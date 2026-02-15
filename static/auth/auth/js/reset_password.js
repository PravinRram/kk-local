const newPasswordInput = document.getElementById("reset-password");
const confirmPasswordInput = document.getElementById("reset-confirm-password");
const checklist = document.querySelector("[data-password-checklist]");

const passwordChecks = {
  length: (value) => value.length >= 8,
  upper: (value) => /[A-Z]/.test(value),
  lower: (value) => /[a-z]/.test(value),
  number: (value) => /[0-9]/.test(value),
};

const updatePasswordState = () => {
  if (!newPasswordInput || !checklist) return;
  const value = newPasswordInput.value;
  let isValid = true;
  checklist.querySelectorAll("li").forEach((item) => {
    const key = item.dataset.check;
    const passed = passwordChecks[key](value);
    item.classList.toggle("done", passed);
    if (!passed) isValid = false;
  });

  if (!value) {
    newPasswordInput.setCustomValidity("Password is required.");
  } else if (!isValid) {
    newPasswordInput.setCustomValidity(
      "Use at least 8 characters, with uppercase, lowercase, and a number."
    );
  } else {
    newPasswordInput.setCustomValidity("");
  }

  if (confirmPasswordInput) {
    const confirmValue = confirmPasswordInput.value;
    if (confirmValue && value !== confirmValue) {
      confirmPasswordInput.setCustomValidity("Passwords do not match.");
    } else {
      confirmPasswordInput.setCustomValidity("");
    }
  }
};

if (newPasswordInput && checklist) {
  updatePasswordState();
  newPasswordInput.addEventListener("input", updatePasswordState);
  newPasswordInput.addEventListener("blur", updatePasswordState);
}

if (confirmPasswordInput) {
  confirmPasswordInput.addEventListener("input", updatePasswordState);
  confirmPasswordInput.addEventListener("blur", updatePasswordState);
}
