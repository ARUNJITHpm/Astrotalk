// Tara auth page — login / register, then hand off to the chat at "/".
(() => {
  const tabLogin = document.getElementById("tab-login");
  const tabRegister = document.getElementById("tab-register");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const resetForm = document.getElementById("reset-form");
  const loginError = document.getElementById("login-error");
  const regError = document.getElementById("reg-error");
  const resetError = document.getElementById("reset-error");
  const tabs = document.querySelector(".tabs");
  const sub = document.getElementById("sub");

  // Already signed in (number AND a live session token)? Skip to the chat.
  // Old sessions that predate tokens fall through to login again.
  if (localStorage.getItem("tara_phone") && localStorage.getItem("tara_token")) {
    window.location.replace("/");
    return;
  }

  // Mirror identity.service.normalize_phone (leading + kept, digits only) so the
  // same number is one key across SQL charts + Mongo history/memory.
  const normalizePhone = (raw) => {
    const s = raw.trim();
    const digits = s.replace(/\D/g, "");
    return s.startsWith("+") ? "+" + digits : digits;
  };

  function showError(el, msg) {
    el.textContent = msg;
    el.hidden = false;
  }

  function enter(phone, user, token) {
    localStorage.setItem("tara_phone", phone);
    // Bearer session token (47h TTL) — sent on every user-scoped API call.
    if (token) localStorage.setItem("tara_token", token);
    // Remember the display name so the chat can greet the user by name.
    if (user && user.name) localStorage.setItem("tara_name", user.name);
    else localStorage.removeItem("tara_name");
    // Cache the full profile so the chat can show a details/profile section
    // without re-fetching sensitive birth data.
    if (user) {
      localStorage.setItem(
        "tara_profile",
        JSON.stringify({
          id: user.id,
          phone: user.phone || phone,
          name: user.name,
          dob: user.dob,
          birth_time: user.birth_time,
          birth_place: user.birth_place,
          tz: user.tz,
        })
      );
    }
    window.location.href = "/";
  }

  // --- Tab switching ---
  function selectTab(mode) {
    const login = mode !== "register";
    // Leaving the (tab-less) reset flow: restore the tab bar.
    tabs.hidden = false;
    resetForm.hidden = true;
    tabLogin.classList.toggle("active", login);
    tabRegister.classList.toggle("active", !login);
    loginForm.hidden = !login;
    registerForm.hidden = login;
    loginError.hidden = true;
    regError.hidden = true;
    sub.textContent = login
      ? "താരയിലേക്ക് പ്രവേശിക്കൂ"
      : "താരയുമായി തുടങ്ങാൻ ഒരു അക്കൗണ്ട് ഉണ്ടാക്കൂ";
  }
  tabLogin.addEventListener("click", () => selectTab("login"));
  tabRegister.addEventListener("click", () => selectTab("register"));

  // --- Forgot password: a self-contained view (no tabs) with two steps ---
  const resetStep1 = document.getElementById("reset-step1");
  const resetStep2 = document.getElementById("reset-step2");
  const resetSubmit = document.getElementById("reset-submit");

  function showReset() {
    // Hand off the number they were already typing, if any.
    const typed = document.getElementById("login-phone").value;
    if (typed) document.getElementById("reset-phone").value = typed;
    tabs.hidden = true;
    loginForm.hidden = true;
    registerForm.hidden = true;
    resetForm.hidden = false;
    // Always start at step 1 (identity), not a stale step 2.
    resetStep1.hidden = false;
    resetStep2.hidden = true;
    resetError.hidden = true;
    resetSubmit.textContent = "തുടരുക →";
    sub.textContent = "പാസ്‌വേഡ് പുനഃസജ്ജമാക്കൂ";
  }
  document.getElementById("forgot-link").addEventListener("click", showReset);
  document.getElementById("reset-back").addEventListener("click", () => selectTab("login"));

  // Step 1 — prove identity, then reveal the new-password step.
  async function resetVerifyStep() {
    const phone = normalizePhone(document.getElementById("reset-phone").value);
    const name = document.getElementById("reset-name").value.trim();
    const dob = document.getElementById("reset-dob").value;
    if (!phone || !name || !dob) {
      showError(resetError, "മൊബൈൽ നമ്പർ, പേര്, ജനന തീയതി — എല്ലാം നൽകൂ.");
      return;
    }
    resetSubmit.disabled = true;
    try {
      const res = await fetch("/identity/password/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, name, dob }),
      });
      if (res.status === 401) {
        showError(resetError, "ഈ വിവരങ്ങൾ ഒരു അക്കൗണ്ടുമായി പൊരുത്തപ്പെടുന്നില്ല.");
        return;
      }
      if (!res.ok) throw new Error("verify failed");
      resetStep1.hidden = true;
      resetStep2.hidden = false;
      resetSubmit.textContent = "പാസ്‌വേഡ് പുതുക്കൂ →";
      document.getElementById("reset-password").focus();
    } catch (err) {
      showError(resetError, "ക്ഷമിക്കണം, എന്തോ പിശക്. വീണ്ടും ശ്രമിക്കൂ.");
    } finally {
      resetSubmit.disabled = false;
    }
  }

  // Step 2 — set the new password (server re-verifies), then log straight in.
  async function resetPasswordStep() {
    const phone = normalizePhone(document.getElementById("reset-phone").value);
    const name = document.getElementById("reset-name").value.trim();
    const dob = document.getElementById("reset-dob").value;
    const pw = document.getElementById("reset-password").value;
    const pw2 = document.getElementById("reset-password2").value;
    if (pw.length < 4) {
      showError(resetError, "പാസ്‌വേഡ് കുറഞ്ഞത് 4 അക്ഷരം വേണം.");
      return;
    }
    if (pw !== pw2) {
      showError(resetError, "രണ്ട് പാസ്‌വേഡുകളും ഒരുപോലെ ആയിരിക്കണം.");
      return;
    }
    resetSubmit.disabled = true;
    try {
      const res = await fetch("/identity/password/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, name, dob, new_password: pw }),
      });
      if (res.status === 401) {
        // Identity changed under us (rare) — send them back to step 1.
        showError(resetError, "ഈ വിവരങ്ങൾ ഒരു അക്കൗണ്ടുമായി പൊരുത്തപ്പെടുന്നില്ല.");
        resetStep2.hidden = true;
        resetStep1.hidden = false;
        resetSubmit.textContent = "തുടരുക →";
        return;
      }
      if (!res.ok) throw new Error("reset failed");
      const data = await res.json(); // AuthResponse — {user, token, expires_at}
      enter(phone, data.user, data.token);
    } catch (err) {
      showError(resetError, "ക്ഷമിക്കണം, എന്തോ പിശക്. വീണ്ടും ശ്രമിക്കൂ.");
    } finally {
      resetSubmit.disabled = false;
    }
  }

  resetForm.addEventListener("submit", (e) => {
    e.preventDefault();
    resetError.hidden = true;
    if (resetStep2.hidden) resetVerifyStep();
    else resetPasswordStep();
  });

  // --- Login: authenticate an existing mobile against SQL ---
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.hidden = true;

    const phone = normalizePhone(document.getElementById("login-phone").value);
    const password = document.getElementById("login-password").value;
    if (!phone || !password) {
      showError(loginError, "മൊബൈൽ നമ്പറും പാസ്‌വേഡും നൽകൂ.");
      return;
    }

    const btn = loginForm.querySelector(".submit");
    btn.disabled = true;
    try {
      const res = await fetch("/identity/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, password }),
      });
      if (res.status === 401) {
        showError(loginError, "മൊബൈൽ നമ്പറോ പാസ്‌വേഡോ തെറ്റാണ്.");
        return;
      }
      if (!res.ok) throw new Error("login failed");
      const data = await res.json(); // AuthResponse — {user, token, expires_at}
      enter(phone, data.user, data.token);
    } catch (err) {
      showError(loginError, "ക്ഷമിക്കണം, എന്തോ പിശക്. വീണ്ടും ശ്രമിക്കൂ.");
    } finally {
      btn.disabled = false;
    }
  });

  // --- Register: create the mobile-keyed account (+ password) in SQL ---
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    regError.hidden = true;

    const phone = normalizePhone(document.getElementById("reg-phone").value);
    const password = document.getElementById("reg-password").value;
    const name = document.getElementById("reg-name").value.trim();
    const dob = document.getElementById("reg-dob").value;
    const birth_time = document.getElementById("reg-time").value || null;
    const birth_place = document.getElementById("reg-place").value.trim();

    if (!phone || !password || !name || !dob || !birth_place) {
      showError(regError, "എല്ലാ വിവരങ്ങളും പൂരിപ്പിക്കൂ.");
      return;
    }
    if (password.length < 4) {
      showError(regError, "പാസ്‌വേഡ് കുറഞ്ഞത് 4 അക്ഷരം വേണം.");
      return;
    }

    const btn = registerForm.querySelector(".submit");
    btn.disabled = true;
    try {
      const res = await fetch("/identity/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone, password, name, dob, birth_time, birth_place,
          ref: new URLSearchParams(window.location.search).get("ref") || null,
        }),
      });
      // Already registered → send them to login with the number pre-filled.
      if (res.status === 409) {
        selectTab("login");
        document.getElementById("login-phone").value = phone;
        showError(loginError, "ഈ നമ്പർ ഇതിനകം രജിസ്റ്റർ ചെയ്തിട്ടുണ്ട് — പ്രവേശിക്കൂ.");
        return;
      }
      if (!res.ok) throw new Error("register failed");
      const data = await res.json(); // AuthResponse — {user, token, expires_at}
      enter(phone, data.user, data.token);
    } catch (err) {
      showError(regError, "ക്ഷമിക്കണം, എന്തോ പിശക്. വീണ്ടും ശ്രമിക്കൂ.");
    } finally {
      btn.disabled = false;
    }
  });
})();
