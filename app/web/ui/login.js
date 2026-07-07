// TARA UI login — login / register / forgot-password against /identity.
// Stores the SAME localStorage keys as the classic UI (tara_token, tara_phone,
// tara_name, tara_profile) so both frontends share one session, then goes to /ui.
(() => {
  const $ = (id) => document.getElementById(id);

  // Already logged in → straight to the chat.
  if (localStorage.getItem("tara_token") && localStorage.getItem("tara_phone")) {
    window.location.replace("/ui");
    return;
  }

  // Mirrors identity.service.normalize_phone: one number = one identity key.
  const normalizePhone = (raw) => {
    const s = raw.trim();
    const digits = s.replace(/\D/g, "");
    return s.startsWith("+") ? "+" + digits : digits;
  };

  // Referral code from a shared link (?ref=CODE) — kept through the visit so
  // it still counts if the user lands, browses, then registers.
  const refCode = new URLSearchParams(window.location.search).get("ref");
  if (refCode) sessionStorage.setItem("tara_ref", refCode);

  const forms = {
    login: $("form-login"),
    register: $("form-register"),
    forgot: $("form-forgot"),
  };
  const tabs = { login: $("tab-login"), register: $("tab-register") };

  function show(which) {
    Object.entries(forms).forEach(([k, f]) => f.classList.toggle("hidden", k !== which));
    tabs.login.classList.toggle("active", which === "login");
    tabs.register.classList.toggle("active", which === "register");
    ["login-error", "register-error", "forgot-error"].forEach((id) =>
      $(id).classList.add("hidden")
    );
  }
  tabs.login.addEventListener("click", () => show("login"));
  tabs.register.addEventListener("click", () => show("register"));
  $("goto-forgot").addEventListener("click", () => {
    show("forgot");
    forgotStep = 1;
    $("forgot-step1").classList.remove("hidden");
    $("forgot-step2").classList.add("hidden");
    $("forgot-submit").textContent = "പരിശോധിക്കൂ →";
  });
  $("back-to-login").addEventListener("click", () => show("login"));

  function setError(id, msg) {
    const el = $(id);
    if (!msg) return el.classList.add("hidden");
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function markInvalid(fieldId) {
    const f = $(fieldId);
    if (!f) return;
    f.classList.add("invalid");
    setTimeout(() => f.classList.remove("invalid"), 900);
  }

  function busy(btnId, on, label) {
    const b = $(btnId);
    b.disabled = on;
    if (label) b.textContent = on ? label : b.dataset.idle || label;
  }

  // Persist the session exactly like the classic UI, then enter the chat.
  function completeAuth(data) {
    localStorage.setItem("tara_token", data.token);
    localStorage.setItem("tara_phone", data.user.phone);
    localStorage.setItem("tara_name", data.user.name || "");
    localStorage.setItem("tara_profile", JSON.stringify(data.user));
    document.body.style.transition = "opacity 0.5s";
    document.body.style.opacity = "0";
    setTimeout(() => window.location.replace("/ui"), 480);
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let detail = null;
    if (!res.ok) {
      try { detail = (await res.json()).detail; } catch (_) { /* non-JSON */ }
      const err = new Error(detail || `HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.status === 204 ? null : res.json();
  }

  // ---------- LOGIN ----------
  forms.login.addEventListener("submit", async (e) => {
    e.preventDefault();
    const phone = normalizePhone($("login-phone").value);
    const password = $("login-password").value;
    if (!phone) return markInvalid("f-login-phone");
    if (!password) return markInvalid("f-login-password");
    setError("login-error", null);
    busy("login-submit", true, "നക്ഷത്രങ്ങൾ നോക്കുന്നു…");
    try {
      const data = await postJson("/identity/login", { phone, password });
      completeAuth(data);
    } catch (err) {
      setError(
        "login-error",
        err.status === 401
          ? "നമ്പറോ പാസ്‌വേഡോ തെറ്റാണ്. വീണ്ടും ശ്രമിക്കൂ."
          : "ബന്ധപ്പെടാൻ കഴിഞ്ഞില്ല — സെർവർ ഓണാണോ?"
      );
      busy("login-submit", false);
      $("login-submit").textContent = "പ്രവേശിക്കൂ ✦";
    }
  });

  // ---------- REGISTER ----------
  forms.register.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("reg-name").value.trim();
    const phone = normalizePhone($("reg-phone").value);
    const password = $("reg-password").value;
    const dob = $("reg-dob").value;
    const birth_time = $("reg-time").value || null;
    const birth_place = $("reg-place").value.trim();
    if (!name) return markInvalid("f-reg-name");
    if (!phone) return markInvalid("f-reg-phone");
    if (password.length < 4) return markInvalid("f-reg-password");
    if (!dob) return markInvalid("f-reg-dob");
    if (!birth_place) return markInvalid("f-reg-place");
    setError("register-error", null);
    busy("register-submit", true, "ജാതകം കണക്കാക്കുന്നു… 🪔");
    try {
      const data = await postJson("/identity/users", {
        name, phone, password, dob, birth_time, birth_place,
        ref: sessionStorage.getItem("tara_ref") || null,
        org: sessionStorage.getItem("tara_org") || null,  // white-label signup
      });
      sessionStorage.removeItem("tara_ref");
      completeAuth(data);
    } catch (err) {
      setError(
        "register-error",
        err.status === 409
          ? "ഈ നമ്പറിൽ ഒരു അക്കൗണ്ട് നിലവിലുണ്ട് — ലോഗിൻ ചെയ്യൂ."
          : err.message && err.status === 422
          ? "വിവരങ്ങൾ ഒന്നുകൂടി പരിശോധിക്കൂ."
          : "രജിസ്ട്രേഷൻ പരാജയപ്പെട്ടു — വീണ്ടും ശ്രമിക്കൂ."
      );
      busy("register-submit", false);
      $("register-submit").textContent = "ജാതകം കണക്കാക്കൂ ✦";
    }
  });

  // ---------- FORGOT (2 steps) ----------
  let forgotStep = 1;
  forms.forgot.addEventListener("submit", async (e) => {
    e.preventDefault();
    const phone = normalizePhone($("fg-phone").value);
    const name = $("fg-name").value.trim();
    const dob = $("fg-dob").value;
    setError("forgot-error", null);

    if (forgotStep === 1) {
      if (!phone || !name || !dob)
        return setError("forgot-error", "എല്ലാ വിവരങ്ങളും നൽകൂ.");
      busy("forgot-submit", true, "പരിശോധിക്കുന്നു…");
      try {
        await postJson("/identity/password/verify", { phone, name, dob });
        forgotStep = 2;
        $("forgot-step1").classList.add("hidden");
        $("forgot-step2").classList.remove("hidden");
        $("forgot-submit").disabled = false;
        $("forgot-submit").textContent = "പാസ്‌വേഡ് മാറ്റൂ ✦";
        $("fg-newpass").focus();
      } catch (err) {
        setError(
          "forgot-error",
          err.status === 401
            ? "വിവരങ്ങൾ ഒരു അക്കൗണ്ടുമായി പൊരുത്തപ്പെടുന്നില്ല."
            : "പരിശോധന പരാജയപ്പെട്ടു — വീണ്ടും ശ്രമിക്കൂ."
        );
        busy("forgot-submit", false);
        $("forgot-submit").textContent = "പരിശോധിക്കൂ →";
      }
      return;
    }

    // step 2 — set the new password (server re-verifies identity)
    const new_password = $("fg-newpass").value;
    if (new_password.length < 4)
      return setError("forgot-error", "പാസ്‌വേഡിന് കുറഞ്ഞത് 4 അക്ഷരം വേണം.");
    busy("forgot-submit", true, "മാറ്റുന്നു…");
    try {
      const data = await postJson("/identity/password/reset", {
        phone, name, dob, new_password,
      });
      completeAuth(data); // reset logs the user straight in
    } catch (err) {
      setError("forgot-error", "മാറ്റാൻ കഴിഞ്ഞില്ല — വീണ്ടും ശ്രമിക്കൂ.");
      busy("forgot-submit", false);
      $("forgot-submit").textContent = "പാസ്‌വേഡ് മാറ്റൂ ✦";
    }
  });
})();
