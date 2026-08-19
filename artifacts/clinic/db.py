"""
db.py — Database layer for Meridian Family Health
─────────────────────────────────────────────────
All Supabase reads/writes live here, kept separate from app.py so the
web layer never talks to the database directly. app.py calls these
functions; this file is the only place that knows about Supabase.

Requires two Replit Secrets:
  SUPABASE_URL  — your project URL   (https://xxxx.supabase.co)
  SUPABASE_KEY  — the anon public key
"""

import os
from datetime import datetime
from supabase import create_client, Client

# ─── Connect once at import ───────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_supabase: Client | None = None


def get_client() -> Client | None:
    """Return a cached Supabase client, or None if not configured."""
    global _supabase
    if _supabase is not None:
        return _supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("WARNING: SUPABASE_URL / SUPABASE_KEY not set — DB calls will fail.")
        return None
    _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ══════════════════════════════════════════════════════════════════
#  READ FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def get_all_patients():
    """Return a list of all patients (basic fields) for the search page."""
    sb = get_client()
    if not sb:
        return []
    try:
        resp = sb.table("patients").select("*").order("name").execute()
        return resp.data or []
    except Exception as e:
        print(f"get_all_patients error: {e}")
        return []


def get_doctor(doctor_id):
    """Return a single doctor row, or None."""
    sb = get_client()
    if not sb or not doctor_id:
        return None
    try:
        resp = sb.table("doctors").select("*").eq("id", doctor_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"get_doctor error: {e}")
        return None


def get_last_vitals(patient_id, limit_per_type=3):
    """
    Return vitals grouped by type, each with its most recent `limit_per_type`
    readings (newest first). Shape:
      { "Blood Pressure": [ {reading, unit, recorded_at}, ... ], ... }
    """
    sb = get_client()
    if not sb:
        return {}
    try:
        resp = (
            sb.table("vitals")
            .select("*")
            .eq("patient_id", patient_id)
            .order("recorded_at", desc=True)
            .execute()
        )
        rows = resp.data or []
        grouped = {}
        for row in rows:
            vt = row["vital_type"]
            grouped.setdefault(vt, [])
            if len(grouped[vt]) < limit_per_type:
                grouped[vt].append({
                    "reading": row["reading"],
                    "unit": row.get("unit", ""),
                    "recorded_at": row["recorded_at"],
                })
        return grouped
    except Exception as e:
        print(f"get_last_vitals error: {e}")
        return {}


def get_clinical_notes(patient_id, limit=5):
    """Return the most recent clinical notes for a patient (newest first)."""
    sb = get_client()
    if not sb:
        return []
    try:
        resp = (
            sb.table("clinical_notes")
            .select("*")
            .eq("patient_id", patient_id)
            .order("note_date", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        print(f"get_clinical_notes error: {e}")
        return []


def get_patient_full(patient_id):
    """
    Assemble a complete patient object for the detail page:
    patient fields + assigned doctor + last-3 vitals + recent clinical notes.
    Returns None if the patient doesn't exist.
    """
    sb = get_client()
    if not sb:
        return None
    try:
        resp = sb.table("patients").select("*").eq("id", patient_id).limit(1).execute()
        if not resp.data:
            return None
        patient = resp.data[0]

        # conditions / medications are stored as jsonb → already lists
        patient["conditions"] = patient.get("conditions") or []
        patient["medications"] = patient.get("medications") or []

        # Attach related data
        patient["doctor"] = get_doctor(patient.get("assigned_doctor_id"))
        patient["vitals_grouped"] = get_last_vitals(patient_id, 3)
        patient["notes"] = get_clinical_notes(patient_id, 5)

        return patient
    except Exception as e:
        print(f"get_patient_full error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  WRITE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def save_handoff_note(patient_id, note_content, ai_summary,
                      priority_level, risk_keywords, doctor_username):
    """Insert one handoff note. Returns the inserted row, or None on failure."""
    sb = get_client()
    if not sb:
        return None
    try:
        resp = sb.table("handoff_notes").insert({
            "patient_id": patient_id,
            "note_content": note_content,
            "ai_summary": ai_summary,
            "priority_level": priority_level,
            "risk_keywords": risk_keywords,
            "doctor_username": doctor_username,
        }).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"save_handoff_note error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  ADMIN STATS  (real numbers, computed from handoff_notes)
# ══════════════════════════════════════════════════════════════════

def get_admin_stats():
    """
    Compute live dashboard stats from the handoff_notes table plus
    a patient-name lookup for the activity log.
    """
    sb = get_client()
    empty = {
        "total_patients_viewed": 0,
        "total_summaries_generated": 0,
        "total_failed_generations": 0,
        "activity_log": [],
        "daily_summaries": [],
        "priority_breakdown": {},
    }
    if not sb:
        return empty

    try:
        notes_resp = (
            sb.table("handoff_notes")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        notes = notes_resp.data or []

        # Patient id → name lookup
        pats = get_all_patients()
        name_by_id = {p["id"]: p["name"] for p in pats}

        total = len(notes)
        failed = sum(1 for n in notes if not n.get("ai_summary"))
        generated = total - failed

        # Activity log (most recent 12)
        activity = []
        for n in notes[:12]:
            created = n.get("created_at", "")
            # Trim ISO timestamp to "YYYY-MM-DD HH:MM"
            ts = created.replace("T", "  ")[:16] if created else ""
            activity.append({
                "timestamp": ts,
                "doctor": n.get("doctor_username", "—"),
                "patient": name_by_id.get(n.get("patient_id"), n.get("patient_id", "—")),
                "action": "Generated Summary" if n.get("ai_summary") else "Summary Failed",
                "priority": n.get("priority_level", ""),
            })

        # Daily counts (last 7 distinct days present in data)
        daily = {}
        for n in notes:
            created = n.get("created_at", "")
            day = created[:10] if created else "unknown"
            daily[day] = daily.get(day, 0) + 1
        daily_sorted = sorted(daily.items())[-7:]
        daily_summaries = [{"date": d[5:], "count": c} for d, c in daily_sorted]

        # Priority breakdown
        pb = {}
        for n in notes:
            lvl = n.get("priority_level", "UNKNOWN") or "UNKNOWN"
            pb[lvl] = pb.get(lvl, 0) + 1

        return {
            "total_patients_viewed": total,          # proxy: every note = a viewed patient
            "total_summaries_generated": generated,
            "total_failed_generations": failed,
            "activity_log": activity,
            "daily_summaries": daily_summaries,
            "priority_breakdown": pb,
        }
    except Exception as e:
        print(f"get_admin_stats error: {e}")
        return empty