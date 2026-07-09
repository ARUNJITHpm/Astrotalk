"""Public service for the whatsapp module — Channel broadcast + 1:1 cap + WAHA chat.

This is the ONLY surface other modules may depend on (AGENTS.md).

HARD GUARDRAILS (GUARDRAILS.md §3 — enforced here, never weakened):
  - Every proactive message carries an AI disclosure + opt-out footer. We append
    it IN CODE, so it cannot be lost by a prompt forgetting it.
  - Business-initiated 1:1 sends are capped at MAX_WA_MESSAGES_PER_DAY per phone
    per 24h, enforced by a counter (see consent.WAMessageLog), not by hand.
  - Opt-in is required before any PROACTIVE send (see consent.is_opted_in).
  - User-initiated WhatsApp chat (WAHA integration): full two-way AI chat is
    allowed per owner approval (2026-07-09). Every reply carries the AI
    disclosure. The daily cap does NOT apply to user-initiated messages.
  - NO function joins or adds a bot to a WhatsApp group. Prohibited.
"""

import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp import consent
from app.modules.whatsapp import onboarding as ob
from app.modules.whatsapp.waha_client import WAHAClient
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# GUARDRAILS.md §3 hard cap; default 3, overridable per environment.
MAX_WA_MESSAGES_PER_DAY = int(os.getenv("MAX_WA_MESSAGES_PER_DAY", "3"))

# Appended to EVERY proactive message. AI disclosure + friction-free opt-out.
_AI_DISCLOSURE = "🤖 ഈ സന്ദേശം AI സഹായത്തോടെ തയ്യാറാക്കിയതാണ്."
_OPT_OUT = "ഈ സന്ദേശങ്ങൾ വേണ്ടെങ്കിൽ 'STOP' എന്ന് മറുപടി അയക്കൂ."
_FOOTER = f"\n\n{_AI_DISCLOSURE}\n{_OPT_OUT}"

# Max messages to keep in the rolling chat context for multi-turn WhatsApp chat.
_MAX_CONTEXT_TURNS = 10  # 10 messages = 5 user + 5 assistant turns

# Opt-out / opt-in keywords (case-insensitive).
_STOP_KEYWORDS = {"stop", "unsubscribe", "quit", "നിർത്തൂ"}
_START_KEYWORDS = {"start", "subscribe", "hi", "hello", "ഹായ്", "നമസ്കാരം"}


def _with_footer(message: str) -> str:
    return f"{message}{_FOOTER}"


class WhatsappService:
    def __init__(self) -> None:
        self._waha = WAHAClient()

    # ---- Channel broadcast (existing, unchanged) ----

    async def publish_to_channel(self, message: str) -> str:
        """Publish ONE message to the WhatsApp Channel, with the compliance footer
        appended automatically. Returns the composed message that was sent/logged.

        MOCK_WHATSAPP=true (default) logs instead of calling the BSP, so the daily
        pipeline runs with no credentials. The first live send needs human
        approval (AGENTS.md).
        """
        composed = _with_footer(message)
        if get_settings().mock_whatsapp:
            logger.info("whatsapp(mock): would publish to Channel:\n%s", composed)
            return composed
        return await self._send_via_bsp(composed)

    async def should_throttle(self, session: AsyncSession, phone: str) -> bool:
        """True if this phone has hit the 24h cap (for future 1:1 sends)."""
        count = await consent.sends_in_last_24h(session, phone)
        return count >= MAX_WA_MESSAGES_PER_DAY

    async def send_template(
        self, session: AsyncSession, phone: str, message: str
    ) -> bool:
        """One business-initiated 1:1 template send, guardrails enforced HERE:

          1. opt-in required (consent ledger) — else silently skipped;
          2. 24h cap respected — else silently skipped;
          3. AI disclosure + opt-out footer appended in code;
          4. the send is logged so the cap keeps counting.

        Returns True only when the message was actually sent (or mock-sent).
        Callers (festival notifications, booking confirmations) NEVER bypass
        this path (GUARDRAILS.md §3).
        """
        if not await consent.is_opted_in(session, phone):
            logger.info("whatsapp: skipped 1:1 send — no opt-in.")
            return False
        if await self.should_throttle(session, phone):
            logger.info("whatsapp: skipped 1:1 send — 24h cap reached.")
            return False
        composed = _with_footer(message)
        if get_settings().mock_whatsapp:
            logger.info("whatsapp(mock): would send 1:1 template:\n%s", composed)
        else:  # pragma: no cover - needs live BSP + human approval
            await self._send_via_bsp(composed)
        await consent.record_send(session, phone)
        return True

    async def _send_via_bsp(self, composed: str) -> str:  # pragma: no cover
        raise NotImplementedError(
            "Live WhatsApp send not wired. Set MOCK_WHATSAPP=false and implement "
            "the BSP call here — the FIRST live send requires human approval "
            "(AGENTS.md / GUARDRAILS.md §3)."
        )

    # ---- WAHA inbound message handler (new) ----

    async def handle_inbound_message(
        self, session: AsyncSession, phone: str, text: str
    ) -> str:
        """Process an inbound WhatsApp message end-to-end.

        This is the core orchestrator for two-way WhatsApp chat:
          1. Check for STOP/START keywords → handle opt-out/opt-in.
          2. Look up the wa_session (create if new).
          3. Check if the user already exists in identity (registered on web).
          4. If onboarding incomplete → run the FSM.
          5. If registered → route to ChatService.handle_message().
          6. Return the reply text. The router sends it via WAHAClient.

        The daily cap does NOT apply here — these are user-initiated messages.
        The AI disclosure is appended by WAHAClient.send_text(), not here.
        """
        text = (text or "").strip()
        lower = text.lower()

        # --- Step 1: opt-out / opt-in keywords ---
        if lower in _STOP_KEYWORDS:
            return await self._handle_stop(session, phone)
        if lower in _START_KEYWORDS:
            wa = await ob.get_session(session, phone)
            if wa is not None and wa.state == "opted_out":
                return await self._handle_start(session, phone)
            # If not opted out, START/hi/hello falls through to normal chat.

        # --- Step 2: get or create wa_session ---
        wa = await ob.get_or_create_session(session, phone)

        # If opted out, remind them.
        if wa.state == "opted_out":
            return (
                "നിങ്ങൾ unsubscribe ചെയ്‌തിരിക്കുന്നു. "
                "തിരികെ വരാൻ *START* എന്ന് അയക്കൂ."
            )

        # --- Step 3: check if user already exists in identity ---
        if wa.state in ("greeting", "ask_name", "ask_dob", "ask_time", "ask_place", "ask_password"):
            existing_user = await self._lookup_user(session, phone)
            if existing_user is not None:
                # User registered on the website — skip onboarding.
                wa.state = "chatting"
                wa.conversation_id = str(uuid.uuid4())
                wa.onboarding_data = None
                await session.flush()
                return ob.EXISTING_USER_MSG.format(name=existing_user.name)

        # --- Step 4: onboarding FSM ---
        if wa.state != "chatting":
            reply, is_complete = await ob.process_onboarding_step(wa, text)
            await session.flush()

            if is_complete:
                # Registration: create user + chart via identity service.
                reply = await self._register_user(session, wa)

            return reply

        # --- Step 5: route to ChatService ---
        return await self._handle_chat(session, wa, text)

    async def _handle_stop(self, session: AsyncSession, phone: str) -> str:
        """Handle STOP keyword — opt the user out."""
        await consent.opt_out(session, phone)
        wa = await ob.get_or_create_session(session, phone)
        wa.state = "opted_out"
        await session.flush()
        return ob.OPT_OUT_MSG

    async def _handle_start(self, session: AsyncSession, phone: str) -> str:
        """Handle START keyword — re-opt the user in."""
        await consent.opt_in(session, phone)
        wa = await ob.get_or_create_session(session, phone)
        # Check if user already exists — if so, go straight to chatting.
        existing = await self._lookup_user(session, phone)
        if existing is not None:
            wa.state = "chatting"
            wa.conversation_id = wa.conversation_id or str(uuid.uuid4())
        else:
            wa.state = "greeting"
            wa.onboarding_data = {}
        await session.flush()
        return ob.OPT_IN_MSG

    async def _lookup_user(self, session: AsyncSession, phone: str):
        """Look up a user by phone via identity's public service.

        Returns the User model instance or None. Never raises.
        """
        try:
            from app.modules.identity.service import IdentityService

            return await IdentityService().get_user_by_phone(session, phone)
        except Exception as exc:
            logger.warning("whatsapp: identity lookup failed (%s); continuing.", exc)
            return None

    async def _register_user(self, session: AsyncSession, wa: ob.WASession) -> str:
        """Create the user account after onboarding completes.

        Uses the same IdentityService.create_user() + chart computation path
        as the web registration, so the user gets a real identity row, chart,
        and can log into the website with the same phone + password.
        """
        import inspect

        from app.modules.astrology_engine.service import AstrologyEngineService
        from app.modules.identity.schemas import UserCreate
        from app.modules.identity.service import IdentityService

        fields = ob.get_onboarding_fields(wa)

        try:
            data = UserCreate(
                phone=fields["phone"],
                password=fields["password"],
                name=fields["name"],
                dob=fields["dob"],
                birth_time=fields.get("birth_time"),
                birth_place=fields["birth_place"],
            )
            identity = IdentityService()

            # Check if user already exists (race: they may have registered
            # on the web while onboarding on WhatsApp).
            existing = await identity.get_user_by_phone(session, data.phone)
            if existing is not None:
                wa.onboarding_data = None
                wa.conversation_id = str(uuid.uuid4())
                await session.flush()
                return ob.EXISTING_USER_MSG.format(name=existing.name)

            user = await identity.create_user(session, data)

            # Compute the natal chart (same as web registration).
            astro = AstrologyEngineService()
            compute = getattr(astro, "compute_natal_chart", None)
            if compute is not None:
                natal = compute(
                    dob=user.dob,
                    birth_time=user.birth_time,
                    lat=user.lat,
                    lng=user.lng,
                    tz=user.tz,
                )
                if inspect.isawaitable(natal):
                    natal = await natal
            else:
                natal = {
                    "status": "pending",
                    "reason": "astrology_engine not yet implemented",
                }
            await identity.save_chart(session, user.id, natal)

            # Mark consent as opted-in (user initiated contact = implied consent).
            await consent.opt_in(session, wa.phone)

            # Clear sensitive onboarding data, set up for chatting.
            wa.onboarding_data = None
            wa.conversation_id = str(uuid.uuid4())
            await session.commit()

            logger.info(
                "whatsapp: new user registered via WhatsApp onboarding (user_id=%s).",
                user.id,
            )
            return ob.REGISTRATION_SUCCESS_MSG

        except Exception as exc:
            logger.error("whatsapp: registration failed (%s)", exc)
            # Roll back the onboarding so they can retry.
            wa.state = "ask_password"
            await session.flush()
            return (
                "❌ രജിസ്‌ട്രേഷൻ പരാജയപ്പെട്ടു. ദയവായി വീണ്ടും ശ്രമിക്കൂ.\n"
                "ഒരു password ടൈപ്പ് ചെയ്യൂ (4+ അക്ഷരങ്ങൾ)."
            )

    async def _handle_chat(
        self, session: AsyncSession, wa: ob.WASession, text: str
    ) -> str:
        """Route a message from a registered user to the Tara brain.

        Uses ChatService.handle_message() — same orchestrator as the website.
        Maintains a rolling context window in wa_sessions.chat_context so
        multi-turn conversations work without the full history reload.
        """
        from app.modules.chat import history, memory
        from app.modules.chat.service import ChatService

        # Build the message list with rolling context.
        context = wa.chat_context or []
        context.append({"role": "user", "content": text})

        try:
            chat_svc = ChatService()
            result = await chat_svc.handle_message(
                user_id=wa.phone,
                messages=context,
                session=session,
            )
            reply = result.reply

            # Append the assistant reply to context and trim.
            context.append({"role": "assistant", "content": reply})
            if len(context) > _MAX_CONTEXT_TURNS * 2:
                context = context[-_MAX_CONTEXT_TURNS * 2 :]
            wa.chat_context = context
            await session.flush()

            # Save history + extract memory (same as the web chat router).
            if not result.is_safety_response:
                try:
                    await history.save_turn(
                        wa.phone,
                        context,
                        reply,
                        wa.conversation_id,
                        llm_provider=result.llm_provider,
                        llm_model=result.llm_model,
                        prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens,
                        total_tokens=result.total_tokens,
                        price_inr=result.price_inr,
                        price_usd=result.price_usd,
                    )
                except Exception as exc:
                    logger.warning("whatsapp: history save failed (%s)", exc)
                try:
                    await memory.extract_memory(wa.phone, context)
                except Exception as exc:
                    logger.warning("whatsapp: memory extraction failed (%s)", exc)

            return reply

        except Exception as exc:
            logger.error("whatsapp: chat failed (%s)", exc)
            return (
                "❌ ക്ഷമിക്കണം, ഒരു പിശക് സംഭവിച്ചു. "
                "ദയവായി വീണ്ടും ശ്രമിക്കൂ."
            )

    # ---- WAHA status (for admin/health) ----

    async def waha_status(self) -> dict:
        """Check the WAHA connection status."""
        return await self._waha.is_healthy()

    async def send_reply(self, phone: str, text: str) -> dict:
        """Send a reply to a WhatsApp user via WAHA.

        Public convenience method so the router doesn't need to instantiate
        WAHAClient directly.
        """
        return await self._waha.send_text(phone, text)

    async def send_reply_raw(self, phone: str, text: str) -> dict:
        """Send a raw reply (no AI disclosure) — for system messages only."""
        return await self._waha.send_text_raw(phone, text)


# Module-level convenience surface.
async def publish_to_channel(message: str) -> str:
    return await WhatsappService().publish_to_channel(message)
