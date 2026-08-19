import os
import sys
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session

import db  # ── our database access layer (db.py) ──

# ─── Require SESSION_SECRET at startup — no fallback ──────────────
_secret_key = os.environ.get("SESSION_SECRET")
if not _secret_key:
    print("FATAL: SESSION_SECRET environment variable is not set.", file=sys.stderr)
    sys.exit(1)

# ─── Gemini API Key ───────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

app = Flask(__name__)
app.secret_key = _secret_key
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
)

# ─── Demo credentials (prototype only — no real patient data) ──────
DEMO_USERS = {
    "dr.sharma": "clinic2026",
    "dr.mehta":  "clinic2026",
    "admin":     "admin2026",
}
ADMIN_USERS = {"admin"}

import requests  # for Gemini call


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


# ══════════════════════════════════════════════════════════════════
#  SMART LOGIC LAYER  (unchanged from Stage 2 — rules, not AI)
# ══════════════════════════════════════════════════════════════════

RISK_KEYWORDS = {
    "critical": [
        "chest pain", "cardiac arrest", "stroke", "seizure", "unconscious",
        "unresponsive", "severe bleeding", "anaphylaxis", "respiratory failure",
        "cardiac", "code blue", "intubation", "crash", "sepsis",
    ],
    "high": [
        "shortness of breath", "high fever", "bleeding", "fall", "fracture",
        "infection", "elevated bp", "hypertensive", "hyperglycemia",
        "hypoglycemia", "non-compliant", "non-adherent", "medication adherence",
        "inconsistent medication", "chest tightness", "dizziness", "fainting",
        "asthma flare", "exacerbation", "prednisone", "urgent", "missed doses",
    ],
    "medium": [
        "pain", "elevated", "increased", "worsening", "fatigue",
        "poor sleep", "insomnia", "anxiety", "nausea", "swelling",
        "referral", "follow-up", "recheck", "monitor", "labs ordered",
        "breathlessness", "migraine",
    ],
}


def detect_risk_keywords(text):
    text_lower = text.lower()
    found = {"critical": [], "high": [], "medium": []}
    for level, keywords in RISK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower and kw not in found[level]:
                found[level].append(kw)
    return found


def assign_priority(risk_keywords, patient):
    conditions = patient.get("conditions", []) or []
    age = patient.get("age", 0) or 0

    if risk_keywords["critical"]:
        return {"level": "CRITICAL", "color": "#dc2626",
                "reason": "Critical risk keywords detected: " + ", ".join(risk_keywords["critical"])}
    if risk_keywords["high"]:
        if len(conditions) >= 3:
            return {"level": "HIGH", "color": "#ea580c",
                    "reason": "High-risk keywords with multiple comorbidities: " + ", ".join(risk_keywords["high"])}
        return {"level": "HIGH", "color": "#ea580c",
                "reason": "High-risk keywords detected: " + ", ".join(risk_keywords["high"])}
    if risk_keywords["medium"]:
        if age >= 65:
            return {"level": "MEDIUM-HIGH", "color": "#d97706",
                    "reason": f"Medium-risk keywords in elderly patient (age {age}): " + ", ".join(risk_keywords["medium"])}
        return {"level": "MEDIUM", "color": "#ca8a04",
                "reason": "Medium-risk keywords detected: " + ", ".join(risk_keywords["medium"])}
    return {"level": "LOW", "color": "#16a34a",
            "reason": "No significant risk keywords detected. Routine follow-up."}


def suggest_actions(risk_keywords, priority, patient):
    actions = []
    conditions_lower = [c.lower() for c in (patient.get("conditions", []) or [])]
    age = patient.get("age", 0) or 0

    if priority["level"] == "CRITICAL":
        actions += ["Immediate physician review required",
                    "Prepare for potential emergency intervention",
                    "Verify all current medications and allergies"]
    elif priority["level"] == "HIGH":
        actions.append("Schedule priority follow-up within 48 hours")
        if any(kw in ["non-compliant", "non-adherent", "inconsistent medication",
                      "medication adherence", "missed doses"] for kw in risk_keywords["high"]):
            actions.append("Medication adherence counseling recommended")
        if any(kw in ["asthma flare", "exacerbation", "shortness of breath"]
               for kw in risk_keywords["high"]):
            actions.append("Monitor respiratory status closely")
        actions.append("Review and reconcile current medications")
    elif priority["level"] in ["MEDIUM", "MEDIUM-HIGH"]:
        actions.append("Schedule follow-up within 1-2 weeks")
        if any(kw in ["labs ordered", "recheck"] for kw in risk_keywords["medium"]):
            actions.append("Ensure pending lab results are reviewed")
        if "referral" in risk_keywords["medium"]:
            actions.append("Confirm referral has been placed and received")
    else:
        actions += ["Continue current care plan",
                    "Schedule routine follow-up per care guidelines"]

    if age >= 65:
        actions.append("Review fall risk assessment")
    if any("diabetes" in c for c in conditions_lower):
        actions.append("Check HbA1c if not done in last 3 months")
    if any("hypertension" in c for c in conditions_lower):
        actions.append("Verify BP log is up to date")
    if any("anemia" in c for c in conditions_lower):
        actions.append("Recheck hemoglobin and iron studies as scheduled")

    # De-dupe while preserving order, cap at 6
    seen, out = set(), []
    for a in actions:
        if a not in seen:
            seen.add(a); out.append(a)
    return out[:6]


# ─── Gemini AI Summary ─────────────────────────────────────────────
def generate_ai_summary(patient, handoff_note):
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured"

    conditions_str = ", ".join(patient.get("conditions", []) or [])
    meds = patient.get("medications", []) or []
    medications_str = "; ".join([f"{m.get('name','')} {m.get('dose','')}" for m in meds])

    # Flatten grouped vitals into a readable string (latest of each type)
    vitals_grouped = patient.get("vitals_grouped", {}) or {}
    vital_bits = []
    for vtype, readings in vitals_grouped.items():
        if readings:
            latest = readings[0]
            vital_bits.append(f"{vtype}: {latest['reading']} {latest.get('unit','')}".strip())
    vitals_str = ", ".join(vital_bits) if vital_bits else "No recent vitals on file"

    past_notes_str = ""
    for note in (patient.get("notes", []) or [])[:3]:
        past_notes_str += f"\n- {note.get('note_date','')} ({note.get('provider','')}): {note.get('content','')}"

    prompt = f"""You are a clinical documentation assistant. Generate a structured, NON-DIAGNOSTIC clinical summary for a patient handoff. This summary will be read by the incoming clinician taking over this patient's care.

PATIENT INFORMATION:
- Name: {patient.get('name','')}
- Age: {patient.get('age','')}, Gender: {patient.get('gender','')}
- Active Conditions: {conditions_str}
- Current Medications: {medications_str}
- Recent Vitals: {vitals_str}

PAST CLINICAL NOTES:{past_notes_str}

CURRENT HANDOFF NOTE FROM OUTGOING CLINICIAN:
{handoff_note}

Generate the summary in exactly these 5 sections. Be concise and clinical. Do NOT make diagnoses or treatment decisions. Use plain text only, no markdown formatting:

1. PATIENT IDENTIFICATION: Brief one-line patient identifier with key demographics.
2. MEDICAL HISTORY & STATUS: Active conditions, current status, recent trends (improving/stable/worsening).
3. CURRENT ASSESSMENT: Key findings from the handoff note and recent vitals. Flag anything needing attention.
4. CLINICAL DETAILS: Current medications, recent changes, pending labs or referrals.
5. PLAN OF CARE: Immediate next steps, pending actions, follow-up timeline, instructions for the incoming clinician.

Keep each section to 2-3 sentences maximum. Be factual and specific."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800},
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text, None
    except requests.exceptions.Timeout:
        return None, "AI service timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return None, f"AI service error: {str(e)}"
    except (KeyError, IndexError) as e:
        return None, f"Unexpected AI response format: {str(e)}"


def parse_summary_sections(raw_summary):
    sections = {
        "patient_identification": "", "medical_history": "",
        "current_assessment": "", "clinical_details": "", "plan_of_care": "",
    }
    section_markers = [
        ("1. PATIENT IDENTIFICATION", "patient_identification"),
        ("2. MEDICAL HISTORY & STATUS", "medical_history"),
        ("3. CURRENT ASSESSMENT", "current_assessment"),
        ("4. CLINICAL DETAILS", "clinical_details"),
        ("5. PLAN OF CARE", "plan_of_care"),
    ]
    current_key = None
    for line in raw_summary.split("\n"):
        s = line.strip()
        if not s:
            continue
        matched = False
        for marker, key in section_markers:
            label = marker.split(". ", 1)[1].lower()
            if marker.lower() in s.lower() or s.lower().startswith(label):
                current_key = key
                parts = s.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    sections[current_key] = parts[1].strip()
                matched = True
                break
        if not matched and current_key:
            sections[current_key] = (sections[current_key] + " " + s).strip()
    if not any(sections.values()):
        sections["patient_identification"] = raw_summary
    return sections


# ══════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════

def _safe_next(url):
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return "/"


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    next_url = _safe_next(request.args.get("next", "") or request.form.get("next", ""))
    if not DEMO_USERS:
        error = "Server is not configured with login credentials."
    elif request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if DEMO_USERS.get(username) == password:
            session["username"] = username
            return redirect(next_url)
        valid_users = ", ".join(sorted(DEMO_USERS.keys()))
        error = f"Invalid username or password. Valid usernames: {valid_users}"
    return render_template("login.html", error=error, next_url=next_url)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    patients = db.get_all_patients()
    return render_template("search.html", patients=patients, username=session.get("username"))


@app.route("/patient/<patient_id>")
@login_required
def patient_detail(patient_id):
    patient = db.get_patient_full(patient_id)
    if not patient:
        return redirect(url_for("index"))
    patients = db.get_all_patients()  # for the nav search dropdown
    return render_template("patient.html", patient=patient, patients=patients,
                           username=session.get("username"))


@app.route("/admin")
@admin_required
def admin():
    stats = db.get_admin_stats()
    return render_template("admin.html", stats=stats, username=session.get("username"))


@app.route("/submit-note", methods=["POST"])
@login_required
def submit_note():
    patient_id = request.form.get("patient_id", "")
    note_content = request.form.get("note_content", "").strip()
    patient = db.get_patient_full(patient_id)

    if not patient or not note_content:
        return redirect(url_for("patient_detail", patient_id=patient_id))

    # ─── Combine text for risk analysis (new note + past notes) ──
    all_notes_text = note_content
    for note in (patient.get("notes", []) or []):
        all_notes_text += " " + note.get("content", "")

    # ─── Smart Logic Layer ───────────────────────────────────────
    risk_keywords = detect_risk_keywords(all_notes_text)
    priority = assign_priority(risk_keywords, patient)
    actions = suggest_actions(risk_keywords, priority, patient)

    # ─── AI Summary ──────────────────────────────────────────────
    ai_summary_raw, ai_error = generate_ai_summary(patient, note_content)
    summary_sections = parse_summary_sections(ai_summary_raw) if ai_summary_raw else None

    # ─── Persist to database ─────────────────────────────────────
    db.save_handoff_note(
        patient_id=patient_id,
        note_content=note_content,
        ai_summary=ai_summary_raw,        # None if AI failed → counts as failure in stats
        priority_level=priority["level"],
        risk_keywords=risk_keywords,
        doctor_username=session.get("username", "unknown"),
    )

    summary_result = {
        "generated": ai_summary_raw is not None,
        "error": ai_error,
        "sections": summary_sections,
        "raw": ai_summary_raw,
        "risk_keywords": risk_keywords,
        "priority": priority,
        "actions": actions,
        "handoff_note": note_content,
        "generated_at": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        "generated_by": session.get("username", "unknown"),
    }

    patients = db.get_all_patients()
    return render_template("patient.html", patient=patient, patients=patients,
                           username=session.get("username"), summary=summary_result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)