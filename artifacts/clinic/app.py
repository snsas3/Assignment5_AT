import os
import sys
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session

# ─── Require SESSION_SECRET at startup — no fallback ──────────────
_secret_key = os.environ.get("SESSION_SECRET")
if not _secret_key:
    print("FATAL: SESSION_SECRET environment variable is not set.", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)
app.secret_key = _secret_key
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Only mark cookies Secure when the app is actually deployed over TLS.
    # In the Replit dev proxy TLS is terminated upstream, so the internal
    # Flask process sees plain HTTP — Secure=True would cause the browser
    # to discard the session cookie on the first redirect.
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
)

# ─── Demo credentials (prototype only — no real patient data) ──────
DEMO_USERS = {
    "dr.patel":  "clinic2026",
    "dr.okafor": "clinic2026",
    "admin":     "admin2026",
}

ADMIN_USERS = {"admin"}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login", next=request.path))
        if session.get("username") not in ADMIN_USERS:
            return render_template("403.html"), 403
        return f(*args, **kwargs)
    return decorated

PATIENTS = [
    {
        "id": "p001",
        "name": "Margaret Chen",
        "dob": "March 14, 1952",
        "age": 73,
        "gender": "Female",
        "phone": "(555) 412-8834",
        "address": "42 Maple Drive, Green Valley, CA 94501",
        "insurance": "Blue Cross Premier — ID: BCX-447291",
        "conditions": [
            "Type 2 Diabetes",
            "Hypertension",
            "Hyperlipidemia",
            "Osteoarthritis (bilateral knees)",
        ],
        "medications": [
            {"name": "Metformin", "dose": "1000 mg twice daily"},
            {"name": "Lisinopril", "dose": "10 mg once daily"},
            {"name": "Atorvastatin", "dose": "40 mg at bedtime"},
            {"name": "Acetaminophen", "dose": "500 mg as needed"},
        ],
        "vitals": {
            "bp": "138/82 mmHg",
            "hr": "74 bpm",
            "temp": "98.4\u00b0F",
            "weight": "168 lbs",
            "height": "5'4\"",
            "o2_sat": "97%",
        },
        "notes": [
            {
                "date": "July 28, 2026",
                "provider": "Dr. Anika Patel",
                "content": "Patient presents for 3-month diabetes follow-up. A1c improved from 7.8 to 7.2. Patient reports improved dietary compliance. Continue current metformin dose. Discussed knee pain management — referred to physical therapy.",
            },
            {
                "date": "May 15, 2026",
                "provider": "Dr. Anika Patel",
                "content": "Hypertension management visit. BP slightly elevated today at 142/88. Patient admits inconsistent medication adherence. Reinforced importance of daily dosing. Added pill organizer as adherence aid. Return in 6 weeks for recheck.",
            },
            {
                "date": "February 10, 2026",
                "provider": "Dr. James Okafor",
                "content": "Annual wellness visit. Routine labs ordered. Lipid panel shows LDL 112 mg/dL — increased atorvastatin from 20 mg to 40 mg. Flu and pneumonia vaccines administered. Mammogram referral placed.",
            },
        ],
    },
    {
        "id": "p002",
        "name": "Robert Nguyen",
        "dob": "November 2, 1978",
        "age": 47,
        "gender": "Male",
        "phone": "(555) 309-7761",
        "address": "11 Birchwood Court, Green Valley, CA 94502",
        "insurance": "Aetna Standard PPO — ID: AET-881034",
        "conditions": [
            "Asthma (moderate persistent)",
            "Seasonal Allergic Rhinitis",
            "Generalized Anxiety Disorder",
        ],
        "medications": [
            {"name": "Fluticasone/Salmeterol (Advair)", "dose": "250/50 mcg inhaled twice daily"},
            {"name": "Albuterol", "dose": "90 mcg inhaled as needed"},
            {"name": "Cetirizine", "dose": "10 mg once daily"},
            {"name": "Sertraline", "dose": "50 mg once daily"},
        ],
        "vitals": {
            "bp": "122/78 mmHg",
            "hr": "68 bpm",
            "temp": "98.7\u00b0F",
            "weight": "182 lbs",
            "height": "5'10\"",
            "o2_sat": "98%",
        },
        "notes": [
            {
                "date": "August 5, 2026",
                "provider": "Dr. James Okafor",
                "content": "Asthma follow-up. Patient reports 2 albuterol uses over the past month — well-controlled. Spirometry shows FEV1 at 82% predicted. No current exacerbations. Discussed peak flow monitoring at home. Continue current regimen.",
            },
            {
                "date": "April 22, 2026",
                "provider": "Dr. Anika Patel",
                "content": "GAD follow-up. Patient rates anxiety 4/10, down from 6/10 last visit. Reports sertraline has been helpful. Continues weekly therapy with Dr. Kim. Sleep has improved. No side effects reported. Continue sertraline 50 mg.",
            },
            {
                "date": "January 17, 2026",
                "provider": "Dr. James Okafor",
                "content": "Urgent visit for asthma flare following respiratory infection. Prescribed 5-day prednisone burst. Albuterol use increased to 3-4x/day. Instructed to return if not improving in 48 hours. Symptoms resolved by follow-up call.",
            },
        ],
    },
    {
        "id": "p003",
        "name": "Dorothy Williamson",
        "dob": "July 19, 1965",
        "age": 60,
        "gender": "Female",
        "phone": "(555) 827-5510",
        "address": "88 Cedarwood Lane, Green Valley, CA 94503",
        "insurance": "Medicare Advantage — Humana HMO — ID: HUM-2291847",
        "conditions": [
            "Hypothyroidism",
            "Chronic Low Back Pain",
            "Gastroesophageal Reflux Disease (GERD)",
            "Insomnia",
        ],
        "medications": [
            {"name": "Levothyroxine", "dose": "75 mcg once daily (morning, fasting)"},
            {"name": "Omeprazole", "dose": "20 mg once daily before breakfast"},
            {"name": "Cyclobenzaprine", "dose": "5 mg at bedtime as needed"},
            {"name": "Melatonin", "dose": "3 mg at bedtime"},
        ],
        "vitals": {
            "bp": "128/80 mmHg",
            "hr": "64 bpm",
            "temp": "97.8\u00b0F",
            "weight": "154 lbs",
            "height": "5'6\"",
            "o2_sat": "99%",
        },
        "notes": [
            {
                "date": "July 10, 2026",
                "provider": "Dr. Anika Patel",
                "content": "Thyroid management visit. TSH 2.4 mIU/L — within normal range. Patient reports fatigue has improved since levothyroxine dose adjustment 3 months ago. GERD symptoms well-controlled on omeprazole. Back pain 3/10 today. Continue current plan.",
            },
            {
                "date": "April 3, 2026",
                "provider": "Dr. James Okafor",
                "content": "Back pain evaluation. MRI lumbar spine reviewed — mild disc bulging at L4-L5, no cord compression. Initiated physical therapy referral. Prescribed cyclobenzaprine for acute spasm. Discussed core strengthening exercises. Avoid heavy lifting.",
            },
            {
                "date": "February 28, 2026",
                "provider": "Dr. Anika Patel",
                "content": "Insomnia follow-up. Patient reports poor sleep quality — averaging 4-5 hours per night. Sleep hygiene counseling provided. Added melatonin 3 mg. Advised limiting screens before bed. TSH due for recheck — labs ordered. Will follow up with results.",
            },
        ],
    },
]

PATIENTS_BY_ID = {p["id"]: p for p in PATIENTS}

ADMIN_STATS = {
    "total_patients_viewed": 47,
    "total_summaries_generated": 23,
    "total_failed_generations": 2,
    "activity_log": [
        {"timestamp": "2026-08-16  14:32", "doctor": "Dr. Anika Patel", "patient": "Margaret Chen", "action": "Viewed Patient"},
        {"timestamp": "2026-08-16  14:35", "doctor": "Dr. Anika Patel", "patient": "Margaret Chen", "action": "Generated Summary"},
        {"timestamp": "2026-08-16  13:55", "doctor": "Dr. James Okafor", "patient": "Robert Nguyen", "action": "Viewed Patient"},
        {"timestamp": "2026-08-16  13:58", "doctor": "Dr. James Okafor", "patient": "Robert Nguyen", "action": "Generated Summary"},
        {"timestamp": "2026-08-16  11:10", "doctor": "Dr. Anika Patel", "patient": "Dorothy Williamson", "action": "Viewed Patient"},
        {"timestamp": "2026-08-16  11:14", "doctor": "Dr. Anika Patel", "patient": "Dorothy Williamson", "action": "Summary Failed"},
        {"timestamp": "2026-08-15  16:02", "doctor": "Dr. James Okafor", "patient": "Margaret Chen", "action": "Generated Summary"},
        {"timestamp": "2026-08-15  15:30", "doctor": "Dr. James Okafor", "patient": "Dorothy Williamson", "action": "Viewed Patient"},
        {"timestamp": "2026-08-15  09:45", "doctor": "Dr. Anika Patel", "patient": "Robert Nguyen", "action": "Viewed Patient"},
        {"timestamp": "2026-08-14  14:20", "doctor": "Dr. James Okafor", "patient": "Robert Nguyen", "action": "Generated Summary"},
    ],
    "daily_summaries": [
        {"date": "Aug 11", "count": 2},
        {"date": "Aug 12", "count": 4},
        {"date": "Aug 13", "count": 3},
        {"date": "Aug 14", "count": 5},
        {"date": "Aug 15", "count": 4},
        {"date": "Aug 16", "count": 5},
    ],
}


def _safe_next(url: str) -> str:
    """Return url only if it's a same-origin relative path; otherwise fall back to '/'."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return "/"


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    next_url = _safe_next(request.args.get("next", "") or request.form.get("next", ""))
    if not DEMO_USERS:
        error = "Server is not configured with login credentials. Set CLINIC_CLINICIAN_PASS and CLINIC_ADMIN_PASS."
    elif request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        print(f"[login] attempt: username={username!r} match={DEMO_USERS.get(username) == password}", flush=True)
        if DEMO_USERS.get(username) == password:
            session["username"] = username
            return redirect(next_url)
        valid_users = ", ".join(sorted(DEMO_USERS.keys()))
        error = f"Invalid username or password. Valid usernames: {valid_users}"
    return render_template("login.html", error=error, next_url=next_url)


@app.route("/_auth_debug")
def auth_debug():
    """Development-only: shows whether credentials are loaded (never shows values)."""
    return {
        "secrets_loaded": {
            "CLINIC_CLINICIAN_PASS": bool(_clinician_pass),
            "CLINIC_ADMIN_PASS":     bool(_admin_pass),
            "SESSION_SECRET":        bool(_secret_key),
        },
        "valid_usernames": sorted(DEMO_USERS.keys()),
        "session_cookie_secure": app.config.get("SESSION_COOKIE_SECURE"),
    }


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("search.html", patients=PATIENTS, username=session.get("username"))


@app.route("/search")
@login_required
def search():
    return redirect(url_for("index"))


@app.route("/patient/<patient_id>")
@login_required
def patient_detail(patient_id):
    patient = PATIENTS_BY_ID.get(patient_id)
    if not patient:
        return redirect(url_for("index"))
    return render_template("patient.html", patient=patient, patients=PATIENTS, username=session.get("username"))


@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", stats=ADMIN_STATS, username=session.get("username"))


@app.route("/submit-note", methods=["POST"])
@login_required
def submit_note():
    patient_id = request.form.get("patient_id", "")
    return redirect(url_for("patient_detail", patient_id=patient_id))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
