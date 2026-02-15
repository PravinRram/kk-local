import base64
import re
from datetime import date, datetime


USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[89]\d{7}$")


def _calculate_age(dob):
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def validate_login(data):
    errors = {}
    identifier = (data.get("identifier") or "").strip()
    password = data.get("password") or ""

    if not identifier:
        errors["identifier"] = "Please enter your username or email."
    if not password:
        errors["password"] = "Please enter your password."

    return len(errors) == 0, errors


def validate_register_step(step, data, files=None):
    errors = {}

    if step == 1:
        username = (data.get("username") or "").strip()
        display_name = (data.get("display_name") or "").strip()

        if not USERNAME_RE.match(username):
            errors["username"] = "Username must be 3–20 characters (letters, numbers, underscore)."
        if not (2 <= len(display_name) <= 40):
            errors["display_name"] = "Display name must be 2–40 characters."
    elif step == 2:
        email = (data.get("email") or "").strip().lower()

        if not EMAIL_RE.match(email):
            errors["email"] = "Please enter a valid email address."
    elif step == 3:
        password = data.get("password") or ""
        password_errors = []
        if len(password) < 8:
            password_errors.append("Password must be at least 8 characters.")
        if not re.search(r"[A-Z]", password):
            password_errors.append("Password must include an uppercase letter.")
        if not re.search(r"[a-z]", password):
            password_errors.append("Password must include a lowercase letter.")
        if not re.search(r"\d", password):
            password_errors.append("Password must include a number.")
        if password_errors:
            errors["password"] = " ".join(password_errors)
    elif step == 4:
        dob_raw = (data.get("date_of_birth") or "").strip()

        if not dob_raw:
            errors["date_of_birth"] = "Please enter your birthday."
        else:
            try:
                dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
                if _calculate_age(dob) < 13:
                    errors["date_of_birth"] = "You must be at least 13 years old."
            except ValueError:
                errors["date_of_birth"] = "Please use a valid date."

    elif step == 5:
        cropped_avatar = (data.get("cropped_avatar") or "").strip()
        if cropped_avatar:
            if not cropped_avatar.startswith("data:image/"):
                errors["profile_picture"] = "Cropped image must be PNG, JPG, or WEBP."
            else:
                try:
                    header, encoded = cropped_avatar.split(",", 1)
                except ValueError:
                    errors["profile_picture"] = "Cropped image is invalid."
                else:
                    if not any(
                        mime in header for mime in ("image/png", "image/jpeg", "image/webp")
                    ):
                        errors["profile_picture"] = "Cropped image must be PNG, JPG, or WEBP."
                    else:
                        try:
                            raw = base64.b64decode(encoded)
                            if len(raw) > 2 * 1024 * 1024:
                                errors["profile_picture"] = "Profile picture must be under 2MB."
                        except Exception:
                            errors["profile_picture"] = "Cropped image is invalid."
        elif files and files.get("profile_picture"):
            filename = files.get("profile_picture").filename.lower()
            if filename and not filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
                errors["profile_picture"] = "Profile picture must be PNG, JPG, or WEBP."

    return len(errors) == 0, errors


def validate_profile_update(data, files=None):
    errors = {}
    username = (data.get("username") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    location = (data.get("location") or "").strip()
    phone = (data.get("phone") or "").strip()
    bio = (data.get("bio") or "").strip()
    website = (data.get("website") or "").strip()
    privacy = (data.get("privacy") or "").strip()
    gender = (data.get("gender") or "").strip()
    age_group = (data.get("age_group") or "").strip()
    dob_raw = (data.get("date_of_birth") or "").strip()

    if username and not USERNAME_RE.match(username):
        errors["username"] = "Username must be 3–20 characters (letters, numbers, underscore)."
    if display_name and not (2 <= len(display_name) <= 40):
        errors["display_name"] = "Display name must be 2–40 characters."
    if location and not (2 <= len(location) <= 20):
        errors["location"] = "Location must be 2–20 characters."
    if phone and not PHONE_RE.match(phone):
        errors["phone"] = "Phone must be 8 digits and start with 8 or 9."
    if len(bio) > 160:
        errors["bio"] = "Bio must be 160 characters or less."
    if privacy and privacy not in {"public", "private"}:
        errors["privacy"] = "Please choose a privacy setting."
    if gender and gender not in {"male", "female"}:
        errors["gender"] = "Please choose male or female."
    if age_group and age_group not in {"youth", "senior"}:
        errors["age_group"] = "Please choose youth or senior."
    if dob_raw:
        try:
            dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
            if _calculate_age(dob) < 13:
                errors["date_of_birth"] = "You must be at least 13 years old."
        except ValueError:
            errors["date_of_birth"] = "Please use a valid date."

    cropped_avatar = (data.get("cropped_avatar") or "").strip()
    if cropped_avatar:
        if not cropped_avatar.startswith("data:image/"):
            errors["profile_picture"] = "Cropped image must be PNG, JPG, or WEBP."
        else:
            try:
                header, encoded = cropped_avatar.split(",", 1)
            except ValueError:
                errors["profile_picture"] = "Cropped image is invalid."
            else:
                if not any(
                    mime in header for mime in ("image/png", "image/jpeg", "image/webp")
                ):
                    errors["profile_picture"] = "Cropped image must be PNG, JPG, or WEBP."
                else:
                    try:
                        raw = base64.b64decode(encoded)
                        if len(raw) > 2 * 1024 * 1024:
                            errors["profile_picture"] = "Profile picture must be under 2MB."
                    except Exception:
                        errors["profile_picture"] = "Cropped image is invalid."
    elif files and files.get("profile_picture"):
        filename = files.get("profile_picture").filename.lower()
        if filename and not filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
            errors["profile_picture"] = "Profile picture must be PNG, JPG, or WEBP."

    return len(errors) == 0, errors


def validate_change_password(data):
    errors = {}
    old_password = data.get("old_password") or ""
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not old_password:
        errors["old_password"] = "Please enter your current password."
    new_password_errors = []
    if len(new_password) < 8:
        new_password_errors.append("New password must be at least 8 characters.")
    if not re.search(r"[A-Z]", new_password):
        new_password_errors.append("New password must include an uppercase letter.")
    if not re.search(r"[a-z]", new_password):
        new_password_errors.append("New password must include a lowercase letter.")
    if not re.search(r"\d", new_password):
        new_password_errors.append("New password must include a number.")
    if new_password_errors:
        errors["new_password"] = " ".join(new_password_errors)
    if new_password != confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    return len(errors) == 0, errors


def validate_forgot_password(data):
    errors = {}
    email = (data.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        errors["email"] = "Please enter a valid email address."
    return len(errors) == 0, errors


def validate_reset_password(data):
    errors = {}
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or ""

    password_errors = []
    if len(password) < 8:
        password_errors.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        password_errors.append("Password must include an uppercase letter.")
    if not re.search(r"[a-z]", password):
        password_errors.append("Password must include a lowercase letter.")
    if not re.search(r"\d", password):
        password_errors.append("Password must include a number.")
    if password_errors:
        errors["password"] = " ".join(password_errors)
    if password != confirm:
        errors["confirm_password"] = "Passwords do not match."

    return len(errors) == 0, errors


def validate_delete_account(data, current_user):
    errors = {}
    confirm_username = (data.get("confirm_username") or "").strip()
    password = data.get("password") or ""

    if confirm_username != current_user.username:
        errors["confirm_username"] = "Please type your username exactly."
    if not password:
        errors["password"] = "Please enter your password."

    return len(errors) == 0, errors
