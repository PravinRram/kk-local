const passwordInput = document.getElementById("password-input");
const checklist = document.querySelector("[data-password-checklist]");

const passwordChecks = {
  length: (value) => value.length >= 8,
  upper: (value) => /[A-Z]/.test(value),
  lower: (value) => /[a-z]/.test(value),
  number: (value) => /[0-9]/.test(value),
};

const updatePasswordChecklist = () => {
  if (!passwordInput || !checklist) return;
  const value = passwordInput.value;
  let isValid = true;
  checklist.querySelectorAll("li").forEach((item) => {
    const key = item.dataset.check;
    const passed = passwordChecks[key](value);
    item.classList.toggle("done", passed);
    if (!passed) isValid = false;
  });
  if (!value) {
    passwordInput.setCustomValidity("Password is required.");
  } else if (!isValid) {
    passwordInput.setCustomValidity(
      "Use at least 8 characters, with uppercase, lowercase, and a number."
    );
  } else {
    passwordInput.setCustomValidity("");
  }
};

if (passwordInput && checklist) {
  updatePasswordChecklist();
  passwordInput.addEventListener("input", updatePasswordChecklist);
  passwordInput.addEventListener("blur", updatePasswordChecklist);
}

document.querySelectorAll(".toggle-password").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.target);
    if (!input) return;
    const isPassword = input.type === "password";
    input.type = isPassword ? "text" : "password";
    button.innerHTML = feather.icons[isPassword ? "eye-off" : "eye"].toSvg();
  });
});

const ageInput = document.querySelector('input[name="age"]');
const dobInput = document.querySelector('input[name="date_of_birth"]');
if (ageInput && dobInput) {
  ageInput.addEventListener("input", () => {
    const age = parseInt(ageInput.value, 10);
    if (Number.isNaN(age) || age <= 0) return;
    const now = new Date();
    const year = now.getFullYear() - age;
    let month = String(now.getMonth() + 1).padStart(2, "0");
    let day = String(now.getDate()).padStart(2, "0");
    if (dobInput.value) {
      const parts = dobInput.value.split("-");
      if (parts.length === 3) {
        month = parts[1];
        day = parts[2];
      }
    }
    dobInput.value = `${year}-${month}-${day}`;
  });
}

const photoInput = document.getElementById("register-photo");
let registerPreviewUrl;
if (photoInput) {
  photoInput.addEventListener("change", () => {
    const file = photoInput.files && photoInput.files[0];
    const label = document.querySelector('label[for="register-photo"]');
    const preview = label ? label.querySelector(".photo-preview") : null;
    if (!file || !preview || !label) return;
    if (registerPreviewUrl) {
      URL.revokeObjectURL(registerPreviewUrl);
    }
    registerPreviewUrl = URL.createObjectURL(file);
    preview.src = registerPreviewUrl;
    label.classList.add("has-preview");
  });
}
