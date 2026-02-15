const guide = document.querySelector("[data-setup-list]");
const photoInput = document.getElementById("profile-picture-input");
const avatar = document.querySelector(".avatar[data-current-avatar]");
const birthdayInput = document.querySelector("[data-setup='birthday']");
const locationInput = document.getElementById("location-input");
const bioInput = document.querySelector("[data-setup='bio']");
const hobbiesWrap = document.querySelector("[data-setup='hobbies']");
const circle = document.querySelector(".setup-circle");
const progressText = document.querySelector(".setup-progress .muted");
const statusText = document.querySelector("[data-setup-status]");
const statusSubtext = document.querySelector("[data-setup-subtext]");

function isPhotoDone() {
  const current = avatar ? avatar.dataset.currentAvatar : "";
  const hasCustom = current && !current.includes("img/default_avatar.png");
  return (photoInput && photoInput.files.length > 0) || hasCustom;
}

function isBasicDone() {
  return Boolean(birthdayInput && birthdayInput.value) &&
    Boolean(locationInput && locationInput.value);
}

function isBioDone() {
  return Boolean(bioInput && bioInput.value.trim().length > 0);
}

function isHobbyDone() {
  if (!hobbiesWrap) return false;
  return Array.from(hobbiesWrap.querySelectorAll("input[type='checkbox']")).some(
    (item) => item.checked
  );
}

function updateGuide() {
  if (!guide) return;
  const steps = {
    photo: isPhotoDone(),
    basic: isBasicDone(),
    bio: isBioDone(),
    hobbies: isHobbyDone(),
  };
  let doneCount = 0;
  guide.querySelectorAll("li").forEach((item) => {
    const key = item.dataset.step;
    const done = steps[key];
    item.classList.toggle("done", done);
    if (done) doneCount += 1;
  });
  if (circle) {
    const percent = Math.round((doneCount / 4) * 100);
    circle.textContent = `${percent}%`;
  }
  if (progressText) {
    progressText.textContent = `${doneCount} of 4 steps completed`;
  }
  const closeBtn = document.querySelector(".setup-close");
  if (closeBtn) {
    closeBtn.classList.toggle("is-hidden", doneCount !== 4);
  }
  if (statusText && statusSubtext) {
    if (doneCount === 4) {
      statusText.textContent = "Completed!";
      statusSubtext.textContent = "Your profile is ready.";
    } else {
      statusText.textContent = "Almost there!";
      statusSubtext.textContent = "Complete the steps.";
    }
  }
}

[photoInput, birthdayInput, locationInput, bioInput].forEach((el) => {
  if (el) {
    el.addEventListener("input", updateGuide);
    el.addEventListener("change", updateGuide);
  }
});
if (hobbiesWrap) {
  hobbiesWrap.addEventListener("change", updateGuide);
}

if (locationInput) {
  let debounceTimer;
  locationInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const query = locationInput.value.trim();
    if (query.length < 2) return;
    debounceTimer = setTimeout(() => {
      fetch(`/api/onemap/search?q=${encodeURIComponent(query)}`)
        .then((res) => res.json())
        .then((data) => {
          const list = document.getElementById("location-list");
          if (!list) return;
          list.innerHTML = "";
          const uniqueItems = Array.from(new Set(data.results || []));
          uniqueItems.forEach((item) => {
            const option = document.createElement("option");
            option.value = item;
            list.appendChild(option);
          });
        })
        .catch(() => {});
    }, 300);
  });
}

const websiteToggle = document.querySelector("[data-toggle='website']");
if (websiteToggle) {
  websiteToggle.addEventListener("click", () => {
    const field = document.querySelector(".optional-field");
    if (field) field.classList.toggle("is-visible");
  });
}

const websiteRemove = document.querySelector("[data-remove='website']");
if (websiteRemove) {
  websiteRemove.addEventListener("click", () => {
    const field = document.querySelector(".optional-field");
    const input = field ? field.querySelector("input[name='website']") : null;
    if (input) input.value = "";
    if (field) field.classList.remove("is-visible");
  });
}

const hobbySearch = document.querySelector("[data-hobby-search]");
if (hobbySearch) {
  hobbySearch.addEventListener("input", () => {
    const term = hobbySearch.value.trim().toLowerCase();
    document.querySelectorAll("[data-hobby-name]").forEach((label) => {
      const name = label.dataset.hobbyName;
      label.style.display = name.includes(term) ? "inline-flex" : "none";
    });
  });
}

const cropPanel = document.querySelector("[data-cropper-panel]");
const cropImage = document.getElementById("cropper-image");
const applyCrop = document.querySelector("[data-apply-crop]");
const croppedField = document.getElementById("cropped-avatar");

let cropper;
let cropObjectUrl;
let previousAvatarSrc = null;

function openCropper(file) {
  if (!cropPanel || !cropImage) return;

  previousAvatarSrc = avatar ? avatar.src : null;

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
}

function closeCropper() {
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
}

if (photoInput) {
  photoInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
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

    if (avatar) avatar.src = dataUrl;

    closeCropper();
    updateGuide();
  });
}

document.querySelectorAll("[data-cancel-crop]").forEach((el) => {
  el.addEventListener("click", () => {
    if (avatar && previousAvatarSrc) avatar.src = previousAvatarSrc;
    if (photoInput) photoInput.value = "";

    closeCropper();
    updateGuide();
  });
});
