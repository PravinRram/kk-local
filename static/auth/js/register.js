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

const registerForm = document.querySelector("form.form");
const stepField = registerForm ? registerForm.querySelector('input[name="step"]') : null;

const setFieldValidity = (field, message) => {
  if (!field) return;
  field.setCustomValidity(message || "");
};

const validateStep1 = () => {
  const usernameInput = registerForm.querySelector('input[name="username"]');
  const displayInput = registerForm.querySelector('input[name="display_name"]');
  const username = (usernameInput?.value || "").trim();
  const displayName = (displayInput?.value || "").trim();
  const usernameOk = /^[A-Za-z0-9_]{3,20}$/.test(username);
  const displayOk = displayName.length >= 2 && displayName.length <= 40;

  setFieldValidity(
    usernameInput,
    usernameOk ? "" : "Username must be 3–20 characters (letters, numbers, underscore)."
  );
  setFieldValidity(
    displayInput,
    displayOk ? "" : "Display name must be 2–40 characters."
  );

  return usernameOk && displayOk;
};

const validateStep2 = () => {
  const emailInput = registerForm.querySelector('input[name="email"]');
  const email = (emailInput?.value || "").trim().toLowerCase();
  const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  setFieldValidity(emailInput, emailOk ? "" : "Please enter a valid email address.");
  return emailOk;
};

const validateStep3 = () => {
  if (!passwordInput) return true;
  updatePasswordChecklist();
  return passwordInput.checkValidity();
};

const calculateAge = (dob) => {
  const today = new Date();
  let years = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
    years -= 1;
  }
  return years;
};

const validateStep4 = () => {
  const dobInput = registerForm.querySelector('input[name="date_of_birth"]');
  const raw = (dobInput?.value || "").trim();
  if (!dobInput) return true;
  if (!raw) {
    setFieldValidity(dobInput, "Please enter your birthday.");
    return false;
  }
  const dob = new Date(raw);
  if (Number.isNaN(dob.getTime())) {
    setFieldValidity(dobInput, "Please use a valid date.");
    return false;
  }
  if (calculateAge(dob) < 13) {
    setFieldValidity(dobInput, "You must be at least 13 years old.");
    return false;
  }
  setFieldValidity(dobInput, "");
  return true;
};

const validateCurrentStep = (step) => {
  if (step === 1) return validateStep1();
  if (step === 2) return validateStep2();
  if (step === 3) return validateStep3();
  if (step === 4) return validateStep4();
  return true;
};

if (registerForm && stepField) {
  registerForm.addEventListener("submit", (event) => {
    const action = (event.submitter && event.submitter.value) || "";
    if (action !== "next" && action !== "create") return;

    const step = Number(stepField.value || "1");
    const ok = validateCurrentStep(step);
    if (!ok) {
      event.preventDefault();
      registerForm.reportValidity();
    }
  });
}


const photoInput = document.getElementById("register-photo");
const croppedField = document.getElementById("register-cropped-avatar");
const cropPanel = document.querySelector("[data-cropper-panel]");
const cropImage = document.getElementById("cropper-image");
const applyCrop = document.querySelector("[data-apply-crop]");

let cropper;
let cropObjectUrl;

const getRegisterPreview = () => {
  const label = document.querySelector('label[for="register-photo"]');
  if (!label) return null;
  return {
    label,
    preview: label.querySelector(".photo-preview"),
  };
};

const openCropper = (file) => {
  if (!cropPanel || !cropImage) return;

  if (cropObjectUrl) URL.revokeObjectURL(cropObjectUrl);
  cropObjectUrl = URL.createObjectURL(file);

  cropPanel.classList.remove("is-hidden");

  cropImage.onload = () => {
    if (cropper) cropper.destroy();
    cropper = new Cropper(cropImage, {
      aspectRatio: 1,
      viewMode: 1,
      dragMode: "move",
      autoCropArea: 1,
      background: false,
    });
  };

  cropImage.src = cropObjectUrl;
};

const closeCropper = () => {
  if (cropper) {
    cropper.destroy();
    cropper = null;
  }
  if (cropObjectUrl) {
    URL.revokeObjectURL(cropObjectUrl);
    cropObjectUrl = null;
  }
  if (cropImage) cropImage.src = "";
  if (cropPanel) cropPanel.classList.add("is-hidden");
};

if (photoInput) {
  photoInput.addEventListener("change", () => {
    const file = photoInput.files && photoInput.files[0];
    if (!file) return;
    if (croppedField) croppedField.value = "";
    openCropper(file);
  });
}

if (applyCrop && croppedField) {
  applyCrop.addEventListener("click", () => {
    if (!cropper) return;

    const canvas = cropper.getCroppedCanvas({ width: 400, height: 400 });
    if (!canvas) return;

    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    croppedField.value = dataUrl;

    const previewState = getRegisterPreview();
    if (previewState && previewState.preview) {
      previewState.preview.src = dataUrl;
      previewState.label.classList.add("has-preview");
    }

    closeCropper();
  });
}

document.querySelectorAll("[data-cancel-crop]").forEach((el) => {
  el.addEventListener("click", () => {
    if (photoInput) photoInput.value = "";
    if (croppedField) croppedField.value = "";
    closeCropper();
  });
});
