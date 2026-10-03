"""
Virutcham Magalir Munnetra Kalzangiam — NGO Website
Full Stack: Flask + Secure Admin Panel + Multi-language Content
+ Donations Dashboard + Razorpay + Twilio SMS
Open Source | MIT License
"""

import os
import json
import csv
import hmac
import hashlib
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from io import StringIO
from datetime import datetime
from functools import wraps
from urllib.parse import urljoin, urlsplit

import razorpay
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, Response
)
from werkzeug.utils import secure_filename
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from public_translations import public_ui

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

# ── Jinja helper: renders a translatable field with live Tamil/Hindi output ───
def trans_field(name, label, value, edit_lang, input_type='input'):
    """
    Renders an input/textarea that — when editing English — shows live
    Tamil and Hindi translations below as the admin types.
    """
    is_en = edit_lang == 'en'
    hint  = '<span class="field-hint">Type English — Tamil &amp; Hindi appear below</span>' if is_en else ''

    if input_type == 'textarea':
        field_html = f'<textarea name="{name}" class="trans-input-en" data-field="{name}" oninput="scheduleTranslation(\'{name}\', this.value)" rows="3">{value}</textarea>'
    else:
        field_html = f'<input type="text" name="{name}" value="{value}" class="trans-input-en" data-field="{name}" oninput="scheduleTranslation(\'{name}\', this.value)"/>'

    if not is_en:
        # Non-English: just show a plain field
        if input_type == 'textarea':
            return f'''<div class="field-group"><label>{label}</label>
              <textarea name="{name}" rows="3">{value}</textarea></div>'''
        else:
            return f'''<div class="field-group"><label>{label}</label>
              <input type="text" name="{name}" value="{value}"/></div>'''

    # English mode: show field + live translation outputs
    return f'''<div class="trans-field-wrap">
      <div class="field-group">
        <label>{label} {hint}</label>
        <div class="trans-field-en">{field_html}</div>
        <div class="trans-field-out">
          <div class="trans-lang-out">
            <div class="trans-lang-out-label">🇮🇳 Tamil (தமிழ்)</div>
            <div class="trans-lang-out-text ta" id="trans-out-ta-{name}"></div>
            <input type="hidden" id="trans-ta-{name}" name="_ta_{name}" value=""/>
          </div>
          <div class="trans-lang-out">
            <div class="trans-lang-out-label">🇮🇳 Hindi (हिन्दी)</div>
            <div class="trans-lang-out-text hi" id="trans-out-hi-{name}"></div>
            <input type="hidden" id="trans-hi-{name}" name="_hi_{name}" value=""/>
          </div>
        </div>
      </div>
    </div>'''

app.jinja_env.globals['trans_field'] = trans_field

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(__file__)
ADMIN_DIR     = os.path.join(BASE_DIR, "admin_data")
CONTENT_FILE  = os.path.join(ADMIN_DIR, "content.json")
DONATIONS_FILE= os.path.join(ADMIN_DIR, "donations.json")
AUTH_FILE     = os.path.join(ADMIN_DIR, "auth.json")
IMAGES_DIR    = os.path.join(BASE_DIR, "static", "images")
GALLERY_DIR   = os.path.join(IMAGES_DIR, "gallery")
ALLOWED_EXT   = {"jpg", "jpeg", "png", "webp", "gif"}

os.makedirs(ADMIN_DIR, exist_ok=True)
os.makedirs(GALLERY_DIR, exist_ok=True)

# ── Razorpay ─────────────────────────────────────────────────────────────────
RAZORPAY_KEY_ID     = os.environ.get("RAZORPAY_KEY_ID",     "rzp_test_XXXXXXXXXXXX")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "your_razorpay_secret")
razorpay_client     = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ── Twilio ───────────────────────────────────────────────────────────────────
TWILIO_SID    = os.environ.get("TWILIO_ACCOUNT_SID",  "ACxxxxxxxxxxxxxx")
TWILIO_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN",   "your_twilio_token")
TWILIO_FROM   = os.environ.get("TWILIO_FROM_NUMBER",  "+1XXXXXXXXXX")
twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)

# ── Admin credentials ──────────────────────────────────────────────────────────
# IMPORTANT: Set these in your .env file — only office staff should know them.
# Donors / website visitors have NO link to /admin anywhere on the public site.
ADMIN_USERNAME = (os.environ.get("ADMIN_USERNAME") or "").strip()
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "").strip()
OFFICE_RECOVERY_EMAIL = os.environ.get("OFFICE_RECOVERY_EMAIL", "").strip().lower()
if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    app.logger.warning(
        "Admin login credentials are not fully configured. Set ADMIN_USERNAME "
        "and ADMIN_PASSWORD in the hosting service environment."
    )
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "").strip()
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
def normalize_public_base_url(base_url):
    if not base_url:
        return ""
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return parsed.geturl().rstrip("/")


PUBLIC_BASE_URL = normalize_public_base_url(os.environ.get("PUBLIC_BASE_URL", ""))

# ── Supported languages ────────────────────────────────────────────────────────
LANGUAGES = {
    "en": "English",
    "ta": "தமிழ் (Tamil)",
    "hi": "हिन्दी (Hindi)",
}
DEFAULT_LANG = "en"

# ── Default website content (per language) ────────────────────────────────────
DEFAULT_FIELDS = {
    "ngo_name":    "Virutcham Magalir Munnetra Kalzangiam",
    "ngo_short":   "Virutcham",
    "ngo_tamil":   "விருட்சம்",
    "ngo_tagline": "Rooted in Community, Rising Together",

    "hero_tag":   "Est. Tamil Nadu, India",
    "hero_line1": "விருட்சம்",
    "hero_line2": "Rooted in Community,",
    "hero_line3": "Rising Together",
    "hero_desc":  "Empowering women · Uplifting transgender lives · Educating children — one shared space at a time.",

    "about_title": "A Tree That Gives Shade to All",
    "about_text1": "Virutcham (விருட்சம்) means Tree in Tamil — a symbol of shelter, growth, and nourishment. We are a grassroots NGO based in Tamil Nadu dedicated to the holistic development of marginalised communities.",
    "about_text2": "Our unique approach transforms a single shared space into a school, kitchen, and living area — a model that honours dignity while maximising impact on shoestring resources.",

    "women_title":  "Women Empowerment",
    "women_desc":   "We provide skill training, financial literacy, legal awareness, and a safe space for women to rebuild their lives and claim their rights.",
    "women_point1": "Tailoring & handicraft training",
    "women_point2": "Financial literacy workshops",
    "women_point3": "Legal aid & counselling",
    "women_point4": "Self-help group formation",

    "trans_title":  "Transgender Empowerment",
    "trans_desc":   "Our transgender outreach program ensures every individual has access to housing support, healthcare referrals, identity document assistance, and dignified livelihood opportunities.",
    "trans_point1": "Safe housing & crisis shelter",
    "trans_point2": "Identity document support",
    "trans_point3": "Healthcare access & referrals",
    "trans_point4": "Employment pathways",

    "children_title":  "Children's Schooling",
    "children_desc":   "In the same room that serves as a school, kitchen, and living space, children learn to read, write, and dream. We provide meals, supplies, tutoring and emotional support.",
    "children_point1": "Free daily meals",
    "children_point2": "School supplies & uniforms",
    "children_point3": "After-school tutoring",
    "children_point4": "Enrolment & retention support",

    "room_title": "One Room. Three Lives Changed.",
    "room_desc":  "A single multi-purpose space that transforms hour by hour — morning classroom for children, afternoon skill centre for women, safe refuge at night for transgender community members.",

    "cta_title": "Your ₹100 feeds a child. Your ₹500 trains a woman. Your ₹1000 changes a life.",
    "cta_desc":  "Every rupee goes directly to the community — no admin overhead, just impact.",

    "footer_tagline": "விருட்சம் — Rooted in Community",
}

# Fields that are NOT translated (same across all languages)
NON_TRANSLATABLE = {
    "ngo_email": "contact@virutcham.org",
    "ngo_phone": "+91XXXXXXXXXX",
    "ngo_address": "Tamil Nadu, India",

    "stat_women":    "500", "stat_trans": "120", "stat_children": "300",
    "stat_years":    "12",  "stat_meals": "50000", "stat_villages": "8",

    "social_facebook": "#", "social_instagram": "#",
    "social_youtube":  "#", "social_whatsapp":  "#",

    # Images
    "img_hero1": "hero1.jpg", "img_hero2": "hero2.jpg", "img_hero3": "hero3.jpg",
    "img_about": "about.jpg", "img_women": "women.jpg", "img_trans": "transgender.jpg",
    "img_children": "children.jpg", "img_room": "room.jpg", "img_donate_side": "donate_side.jpg",
    "img_g1": "gallery/g1.jpg", "img_g2": "gallery/g2.jpg", "img_g3": "gallery/g3.jpg",
    "img_g4": "gallery/g4.jpg", "img_g5": "gallery/g5.jpg", "img_g6": "gallery/g6.jpg",

    # Accessibility / layout settings
    "_font_id":      "default",
    "_color_green":  "#1a7a3c",
    "_color_dark":   "#0d3d20",
    "_color_blue":   "#1a5276",
    "_color_bg":     "#f8fdf9",
    "_font_size":    "normal",   # normal | large | xlarge
    "_high_contrast":"off",      # on | off
    "_reduce_motion":"off",      # on | off
    "_default_lang": "en",
}


# ═════════════════════════════════════════════════════════════════════════════
# CONTENT STORE HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _default_content_struct():
    """Builds default content.json structure with per-language translatable fields."""
    return {
        "languages": {
            lang: DEFAULT_FIELDS.copy() for lang in LANGUAGES
        },
        "shared": NON_TRANSLATABLE.copy(),
    }


def load_content_store():
    if os.path.exists(CONTENT_FILE):
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Backfill any missing languages / fields without overwriting saved data
        defaults = _default_content_struct()
        data.setdefault("languages", {})
        for lang in LANGUAGES:
            data["languages"].setdefault(lang, {})
            for k, v in DEFAULT_FIELDS.items():
                data["languages"][lang].setdefault(k, v)
        data.setdefault("shared", {})
        for k, v in NON_TRANSLATABLE.items():
            data["shared"].setdefault(k, v)
        return data
    store = _default_content_struct()
    save_content_store(store)
    return store


def save_content_store(store):
    with open(CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def get_merged_content(lang=DEFAULT_LANG):
    """Returns a flat dict combining the chosen language's text + shared fields."""
    store = load_content_store()
    lang  = lang if lang in LANGUAGES else DEFAULT_LANG
    merged = {}
    merged.update(store["languages"].get(lang, DEFAULT_FIELDS))
    merged.update(store["shared"])
    merged["_current_lang"] = lang
    return merged


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ═════════════════════════════════════════════════════════════════════════════
# DONATIONS LOG HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def load_donations():
    if os.path.exists(DONATIONS_FILE):
        with open(DONATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_donation(record):
    donations = load_donations()
    donations.insert(0, record)  # newest first
    with open(DONATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(donations, f, ensure_ascii=False, indent=2)


def donation_stats():
    donations = load_donations()
    total_amount = sum(d.get("amount", 0) for d in donations if d.get("status") == "success")
    total_count  = len([d for d in donations if d.get("status") == "success"])
    today_str    = datetime.now().strftime("%Y-%m-%d")
    today_amount = sum(
        d.get("amount", 0) for d in donations
        if d.get("status") == "success" and d.get("date", "").startswith(today_str)
    )
    today_count  = len([
        d for d in donations
        if d.get("status") == "success" and d.get("date", "").startswith(today_str)
    ])
    return {
        "total_amount": total_amount,
        "total_count":  total_count,
        "today_amount": today_amount,
        "today_count":  today_count,
    }


# ═════════════════════════════════════════════════════════════════════════════
# AUTH
# ═════════════════════════════════════════════════════════════════════════════

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get("role") != role:
                return redirect(url_for("admin_login", next=request.path))
            return f(*args, **kwargs)
        return decorated
    return decorator


admin_required = role_required("admin")


def load_auth_store():
    if not os.path.exists(AUTH_FILE):
        return {}
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        app.logger.exception("Could not read the admin auth store")
        return {}


if "password_hash" in load_auth_store():
    app.logger.info(
        "A saved admin password hash is present and takes precedence over "
        "ADMIN_PASSWORD."
    )


def save_auth_store(data):
    temporary_file = AUTH_FILE + ".tmp"
    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temporary_file, AUTH_FILE)


def password_hash_fields(password):
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return {"password_salt": salt.hex(), "password_hash": password_hash.hex()}


def verify_admin_password(password):
    auth_data = load_auth_store()
    if "password_hash" not in auth_data:
        return bool(ADMIN_PASSWORD) and hmac.compare_digest(password, ADMIN_PASSWORD)
    try:
        salt = bytes.fromhex(auth_data["password_salt"])
        expected_hash = bytes.fromhex(auth_data["password_hash"])
    except (KeyError, TypeError, ValueError):
        app.logger.warning("The stored admin password hash is invalid.")
        return False
    candidate_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return hmac.compare_digest(candidate_hash, expected_hash)


def password_error(password, confirmation):
    if len(password) < 12:
        return "Use a password with at least 12 characters."
    if password != confirmation:
        return "The new passwords do not match."
    return None


def send_password_reset_email(token):
    if not all((OFFICE_RECOVERY_EMAIL, SMTP_HOST, SMTP_FROM_EMAIL, PUBLIC_BASE_URL)):
        raise RuntimeError("Password recovery email settings are incomplete")

    reset_path = url_for('admin_reset_password', token=token)
    reset_url = urljoin(f"{PUBLIC_BASE_URL}/", reset_path)
    message = EmailMessage()
    message["Subject"] = "Virutcham office account password reset"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = OFFICE_RECOVERY_EMAIL
    message.set_content(
        "A password reset was requested for the Virutcham office account.\n\n"
        f"Use this one-time link within 30 minutes: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    context = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15, context=context) as server:
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls(context=context)
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES  (donors / visitors — no admin access possible here)
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    lang = request.args.get("lang", session.get("site_lang", DEFAULT_LANG))
    if lang not in LANGUAGES:
        lang = DEFAULT_LANG
    session["site_lang"] = lang
    c = get_merged_content(lang)
    return render_template("index.html", c=c, razorpay_key=RAZORPAY_KEY_ID,
                            languages=LANGUAGES, current_lang=lang,
                            ui=public_ui(lang))


@app.route("/donate")
def donate():
    lang = request.args.get("lang", session.get("site_lang", DEFAULT_LANG))
    if lang not in LANGUAGES:
        lang = DEFAULT_LANG
    session["site_lang"] = lang
    c = get_merged_content(lang)
    return render_template("donate.html", c=c, razorpay_key=RAZORPAY_KEY_ID,
                            languages=LANGUAGES, current_lang=lang,
                            ui=public_ui(lang))


@app.route("/create-order", methods=["POST"])
def create_order():
    data   = request.get_json()
    amount = int(float(data.get("amount", 100)) * 100)
    name   = data.get("name", "Donor")
    email  = data.get("email", "")
    phone  = data.get("phone", "")
    cause  = data.get("cause", "general")
    c = get_merged_content(session.get("site_lang", DEFAULT_LANG))

    try:
        order = razorpay_client.order.create(data={
            "amount":   amount,
            "currency": "INR",
            "receipt":  f"rcpt_{phone[-4:] if len(phone) >= 4 else '0000'}_{int(datetime.now().timestamp())}",
            "notes":    {"donor_name": name, "donor_email": email,
                         "donor_phone": phone, "cause": cause, "ngo": c["ngo_name"]},
        })
        return jsonify({"order_id": order["id"], "amount": amount,
                        "currency": "INR", "key": RAZORPAY_KEY_ID,
                        "name": name, "email": email, "phone": phone})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    """
    Verifies the Razorpay signature, logs the donation for the admin
    dashboard, and sends a thank-you SMS with the donated amount to
    the donor's registered mobile number.
    """
    data   = request.get_json()
    oid    = data.get("razorpay_order_id")
    pid    = data.get("razorpay_payment_id")
    sig    = data.get("razorpay_signature")
    amount = int(data.get("amount", 0))     # paise
    name   = data.get("name", "Donor")
    phone  = data.get("phone", "")
    email  = data.get("email", "")
    cause  = data.get("cause", "general")
    c = get_merged_content(session.get("site_lang", DEFAULT_LANG))

    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(), f"{oid}|{pid}".encode(), hashlib.sha256
    ).hexdigest()

    record = {
        "payment_id": pid,
        "order_id":   oid,
        "name":       name,
        "phone":      phone,
        "email":      email,
        "cause":      cause,
        "amount":     amount / 100,
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status":     "failed",
        "sms_sent":   False,
    }

    if expected != sig:
        record["status"] = "signature_failed"
        save_donation(record)
        return jsonify({"success": False, "error": "Payment verification failed"}), 400

    record["status"] = "success"

    # ── Send SMS confirmation with amount donated ──────────────────────────────
    sms_sent = False
    if phone:
        digits = "".join(filter(str.isdigit, phone))
        phone_e164 = f"+91{digits}" if len(digits) == 10 else f"+{digits}"
        try:
            twilio_client.messages.create(
                body=(
                    f"Vanakkam {name}! 🙏\n"
                    f"Thank you for donating ₹{amount/100:.0f} to {c['ngo_name']}.\n"
                    f"Payment ID: {pid}\n"
                    f"Your support empowers our community! 🌿\n"
                    f"- {c['ngo_short']} Team"
                ),
                from_=TWILIO_FROM, to=phone_e164,
            )
            sms_sent = True
        except Exception as e:
            print(f"SMS error: {e}")

    record["sms_sent"] = sms_sent
    save_donation(record)

    return jsonify({"success": True, "payment_id": pid,
                    "amount": amount / 100, "sms_sent": sms_sent})


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN — AUTH ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    message = {
        "changed": "Your password was changed. Sign in with the new password.",
        "reset": "Your password was reset. Sign in with the new password.",
    }.get(request.args.get("status"))
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        valid_user = bool(ADMIN_USERNAME) and hmac.compare_digest(u, ADMIN_USERNAME)
        valid_pass = verify_admin_password(p)
        if valid_user and valid_pass:
            session.clear()
            session["role"] = "admin"
            session.permanent = False
            nxt = request.args.get("next") or url_for("admin_dashboard")
            if not nxt.startswith("/") or nxt.startswith("//") or "\\" in nxt:
                nxt = url_for("admin_dashboard")
            return redirect(nxt)
        error = "Invalid username or password."
    return render_template("admin/login.html", error=error, message=message)

@app.route("/admin/forgot-password", methods=["GET", "POST"])
def admin_forgot_password():
    message = None
    if request.method == "POST":
        entered_email = request.form.get("email", "").strip().lower()
        if OFFICE_RECOVERY_EMAIL and hmac.compare_digest(entered_email, OFFICE_RECOVERY_EMAIL):
            auth_data = load_auth_store()
            last_request = auth_data.get("reset_requested_at", 0)
            now = datetime.now().timestamp()
            if now - last_request >= 60:
                token = secrets.token_urlsafe(32)
                auth_data["reset_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
                auth_data["reset_expires_at"] = now + 1800
                auth_data["reset_requested_at"] = now
                save_auth_store(auth_data)
                try:
                    send_password_reset_email(token)
                except Exception:
                    app.logger.exception("Could not send the office password reset email")
                    auth_data.pop("reset_token_hash", None)
                    auth_data.pop("reset_expires_at", None)
                    save_auth_store(auth_data)
        message = "If the address matches the office recovery email, a reset link will be sent."
    return render_template("admin/password.html", mode="forgot", message=message)


@app.route("/admin/reset-password/<token>", methods=["GET", "POST"])
def admin_reset_password(token):
    auth_data = load_auth_store()
    stored_token_hash = auth_data.get("reset_token_hash", "")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    token_valid = (
        bool(stored_token_hash)
        and hmac.compare_digest(token_hash, stored_token_hash)
        and datetime.now().timestamp() < auth_data.get("reset_expires_at", 0)
    )
    error = None

    if not token_valid:
        error = "This reset link is invalid or has expired. Request a new link."
    elif request.method == "POST":
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        error = password_error(password, confirmation)
        if not error:
            auth_data.update(password_hash_fields(password))
            auth_data.pop("reset_token_hash", None)
            auth_data.pop("reset_expires_at", None)
            auth_data.pop("reset_requested_at", None)
            save_auth_store(auth_data)
            return redirect(url_for("admin_login", status="reset"))

    return render_template(
        "admin/password.html", mode="reset", token=token,
        error=error, token_valid=token_valid,
    )


@app.route("/admin/change-password", methods=["GET", "POST"])
@admin_required
def admin_change_password():
    error = None
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        if not verify_admin_password(current_password):
            error = "Your current password is incorrect."
        else:
            error = password_error(password, confirmation)
        if not error:
            auth_data = load_auth_store()
            auth_data.update(password_hash_fields(password))
            auth_data.pop("reset_token_hash", None)
            auth_data.pop("reset_expires_at", None)
            auth_data.pop("reset_requested_at", None)
            save_auth_store(auth_data)
            session.clear()
            return redirect(url_for("admin_login", status="changed"))

    return render_template("admin/password.html", mode="change", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN — DASHBOARD & CONTENT EDITOR
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/admin")
@admin_required
def admin_dashboard():
    edit_lang = request.args.get("lang", DEFAULT_LANG)
    if edit_lang not in LANGUAGES:
        edit_lang = DEFAULT_LANG
    c = get_merged_content(edit_lang)
    stats = donation_stats()
    return render_template("admin/dashboard.html", c=c, languages=LANGUAGES,
                            edit_lang=edit_lang, stats=stats)


@app.route("/admin/save-text", methods=["POST"])
@admin_required
def admin_save_text():
    edit_lang = request.form.get("_edit_lang", DEFAULT_LANG)
    if edit_lang not in LANGUAGES:
        edit_lang = DEFAULT_LANG

    store = load_content_store()

    for key, value in request.form.items():
        if key in ("_edit_lang",):
            continue

        # Live-translated Tamil values (hidden inputs named _ta_<field>)
        if key.startswith("_ta_"):
            field = key[4:]
            if value.strip() and field in DEFAULT_FIELDS:
                store["languages"]["ta"][field] = value.strip()

        # Live-translated Hindi values (hidden inputs named _hi_<field>)
        elif key.startswith("_hi_"):
            field = key[4:]
            if value.strip() and field in DEFAULT_FIELDS:
                store["languages"]["hi"][field] = value.strip()

        # Normal translatable fields — save to the language being edited
        elif key in DEFAULT_FIELDS:
            store["languages"][edit_lang][key] = value.strip()

        # Shared fields (images, stats, colors, social links etc.)
        elif key in NON_TRANSLATABLE:
            store["shared"][key] = value.strip()

    save_content_store(store)
    return jsonify({"success": True, "message": f"Saved ({LANGUAGES[edit_lang]})"})


@app.route("/admin/upload-image", methods=["POST"])
@admin_required
def admin_upload_image():
    key  = request.form.get("image_key")
    file = request.files.get("image_file")
    store = load_content_store()

    if not file or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Invalid file type. Use JPG, PNG or WebP."})
    if key not in NON_TRANSLATABLE:
        return jsonify({"success": False, "error": "Unknown image key."})

    filename  = secure_filename(store["shared"].get(key, f"{key}.jpg"))
    save_path = os.path.join(IMAGES_DIR, filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)

    return jsonify({
        "success": True, "message": "Image updated!",
        "filename": filename,
        "url": f"/static/images/{filename}?v={os.path.getmtime(save_path):.0f}"
    })


@app.route("/admin/get-content")
@admin_required
def admin_get_content():
    lang = request.args.get("lang", DEFAULT_LANG)
    return jsonify(get_merged_content(lang))


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN — DONATIONS DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/admin/donations")
@admin_required
def admin_donations():
    donations = load_donations()
    stats = donation_stats()
    return render_template("admin/donations.html", donations=donations, stats=stats)


@app.route("/admin/donations/data")
@admin_required
def admin_donations_data():
    """JSON endpoint — lets the dashboard auto-refresh without reloading the page."""
    donations = load_donations()
    stats = donation_stats()
    return jsonify({"donations": donations, "stats": stats})


@app.route("/admin/donations/export")
@admin_required
def admin_donations_export():
    """Download all donations as a CSV file for office records."""
    donations = load_donations()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Date", "Name", "Phone", "Email", "Cause", "Amount (INR)",
                      "Payment ID", "Status", "SMS Sent"])
    for d in donations:
        writer.writerow([
            d.get("date", ""), d.get("name", ""), d.get("phone", ""), d.get("email", ""),
            d.get("cause", ""), d.get("amount", ""), d.get("payment_id", ""),
            d.get("status", ""), "Yes" if d.get("sms_sent") else "No",
        ])
    output = si.getvalue()
    return Response(
        output, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=virutcham_donations.csv"}
    )


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN — LIVE TRANSLATION
# Uses Google Translate free endpoint (no API key needed for small use)
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/admin/translate", methods=["POST"])
@admin_required
def admin_translate():
    """
    Translates English text to Tamil and Hindi live as the admin types.
    Uses Google Translate free endpoint — no API key required for NGO scale.
    Returns both translations in one call.
    """
    import urllib.request, urllib.parse

    data   = request.get_json(silent=True) or {}
    text   = data.get("text", "").strip()
    target = data.get("target", "ta")   # 'ta' = Tamil, 'hi' = Hindi

    if not text:
        return jsonify({"translated": "", "original": text})

    if target not in {"ta", "hi"}:
        return jsonify({"translated": "", "error": "Unsupported target language", "original": text})

    try:
        # Google Translate free endpoint (works for small volume)
        encoded = urllib.parse.quote(text)
        safe_target = urllib.parse.quote(target, safe="")
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=en&tl={safe_target}&dt=t&q={encoded}"
        )
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0"
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
        # Result structure: [[[translated, original, ...], ...], ...]
        translated = "".join(
            part[0] for part in result[0] if part[0]
        )
        return jsonify({"translated": translated, "original": text, "target": target})
    except Exception as e:
        return jsonify({"translated": "", "error": str(e), "original": text})


@app.route("/admin/translate-all", methods=["POST"])
@admin_required
def admin_translate_all():
    """
    Translates ALL current English content into Tamil AND Hindi at once.
    Used by the 'Auto-translate everything' button in admin panel.
    """
    import urllib.request, urllib.parse

    def translate_text(text, target):
        if not text or not text.strip():
            return text
        if target not in {"ta", "hi"}:
            return text
        try:
            encoded = urllib.parse.quote(text[:500])  # limit per call
            safe_target = urllib.parse.quote(target, safe="")
            url = (
                f"https://translate.googleapis.com/translate_a/single"
                f"?client=gtx&sl=en&tl={safe_target}&dt=t&q={encoded}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                result = json.loads(resp.read().decode())
            return "".join(part[0] for part in result[0] if part[0])
        except Exception:
            return text  # fallback to original on error

    store = load_content_store()
    en_content = store["languages"]["en"]
    translated_count = 0

    for target_lang in ["ta", "hi"]:
        for field_key, en_value in en_content.items():
            # Only translate if target lang still has the default English value
            current = store["languages"][target_lang].get(field_key, "")
            if current == en_value or current == DEFAULT_FIELDS.get(field_key, ""):
                translated = translate_text(en_value, target_lang)
                if translated and translated != en_value:
                    store["languages"][target_lang][field_key] = translated
                    translated_count += 1

    save_content_store(store)
    return jsonify({
        "success": True,
        "message": f"Translated {translated_count} fields into Tamil and Hindi.",
        "count": translated_count
    })


# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port,
            debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
