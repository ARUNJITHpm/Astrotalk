"""Send a real WhatsApp message via the official Meta Cloud API — a standalone
smoke test for the ``cloud`` transport.

This does NOT touch the app's settings or DB. Give it a token + phone number id
+ recipient and it fires one message straight at graph.facebook.com, then prints
Meta's response (message id on success, or the diagnostic error code on failure).
Use it to confirm a token works BEFORE flipping ``whatsapp_transport=cloud`` on
the live Space.

The access token is a secret: pass it via the ``META_ACCESS_TOKEN`` env var
(preferred — it won't land in your shell history) or ``--token``. It is never
logged or written to disk.

Usage (PowerShell):
  $env:META_ACCESS_TOKEN = "EAAG..."      # temporary 24h token from API Setup
  python scripts/wa_cloud_send.py --to 919400621156 --phone-number-id 123456789012345

  # custom message + a health check first:
  python scripts/wa_cloud_send.py --to 919400621156 --phone-number-id 1234... \
      --message "Namaskaram from Nitara 🙏" --health

Recipient (``--to``) is BARE international digits: no ``+``, no spaces, no
``@c.us`` (e.g. ``919400621156``). On the FIRST test with a temporary token the
recipient must be added under API Setup → "To" (Meta's allow-list), otherwise
you'll see error 131030 ("recipient not in allowed list").
"""

import argparse
import asyncio
import os
import sys

import httpx


async def _health(client: httpx.AsyncClient, base: str, token: str) -> None:
    resp = await client.get(
        base,
        params={"fields": "verified_name,display_phone_number,quality_rating"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        d = resp.json()
        print(
            f"  health OK — number={d.get('display_phone_number')} "
            f"name={d.get('verified_name')} quality={d.get('quality_rating')}"
        )
    else:
        print(f"  health FAILED — {resp.status_code}: {resp.text[:300]}")


async def main() -> int:
    ap = argparse.ArgumentParser(description="Send one WhatsApp message via the Meta Cloud API.")
    ap.add_argument("--to", required=True, help="recipient, bare intl digits e.g. 919400621156")
    ap.add_argument(
        "--phone-number-id",
        default=os.environ.get("META_PHONE_NUMBER_ID", ""),
        help="sender Phone Number ID (or set META_PHONE_NUMBER_ID)",
    )
    ap.add_argument("--token", default=os.environ.get("META_ACCESS_TOKEN", ""),
                    help="Meta access token (or set META_ACCESS_TOKEN)")
    ap.add_argument("--message", default="✅ Nitara Cloud API test — this is a live message.")
    ap.add_argument("--api-version", default=os.environ.get("META_API_VERSION", "v21.0"))
    ap.add_argument("--health", action="store_true", help="run a phone-number health check first")
    args = ap.parse_args()

    if not args.token:
        print("ERROR: no token. Set META_ACCESS_TOKEN or pass --token.", file=sys.stderr)
        return 2
    if not args.phone_number_id:
        print("ERROR: no phone number id. Set META_PHONE_NUMBER_ID or pass --phone-number-id.",
              file=sys.stderr)
        return 2

    version = args.api_version.strip("/")
    to = args.to.lstrip("+").split("@", 1)[0]
    node = f"https://graph.facebook.com/{version}/{args.phone_number_id}"
    send_url = f"{node}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": args.message},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        if args.health:
            await _health(client, node, args.token)
        print(f"→ sending to {to} via phone_number_id {args.phone_number_id} ({version})")
        resp = await client.post(
            send_url,
            json=payload,
            headers={"Authorization": f"Bearer {args.token}", "Content-Type": "application/json"},
        )
        if resp.status_code == 200:
            data = resp.json()
            mid = (data.get("messages") or [{}])[0].get("id", "?")
            print(f"✅ sent — message id: {mid}")
            return 0
        # Meta returns a JSON error with code + message — the key triage signal.
        print(f"❌ send failed — HTTP {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
