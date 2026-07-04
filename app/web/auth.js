// Tara auth page — login / register, then hand off to the chat at "/".
(() => {
  const tabLogin = document.getElementById("tab-login");
  const tabRegister = document.getElementById("tab-register");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const loginError = document.getElementById("login-error");
  const regError = document.getElementById("reg-error");
  const sub = document.getElementById("sub");

  // Already signed in? Skip straight to the chat.
  if (localStorage.getItem("tara_phone")) {
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

  function enter(phone, user) {
    localStorage.setItem("tara_phone", phone);
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
      const user = await res.json(); // UserOut — full profile
      enter(phone, user);
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
        body: JSON.stringify({ phone, password, name, dob, birth_time, birth_place }),
      });
      // Already registered → send them to login with the number pre-filled.
      if (res.status === 409) {
        selectTab("login");
        document.getElementById("login-phone").value = phone;
        showError(loginError, "ഈ നമ്പർ ഇതിനകം രജിസ്റ്റർ ചെയ്തിട്ടുണ്ട് — പ്രവേശിക്കൂ.");
        return;
      }
      if (!res.ok) throw new Error("register failed");
      const user = await res.json(); // UserOut — full profile
      enter(phone, user);
    } catch (err) {
      showError(regError, "ക്ഷമിക്കണം, എന്തോ പിശക്. വീണ്ടും ശ്രമിക്കൂ.");
    } finally {
      btn.disabled = false;
    }
  });
})();
