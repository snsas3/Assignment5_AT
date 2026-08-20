"""
db.py — Database layer for Meridian Family Health
─────────────────────────────────────────────────
All Supabase reads/writes live here, kept separate from app.py.

Requires two Replit Secrets:
  SUPABASE_URL  — your project URL   (https://xxxx.supabase.co)
  SUPABASE_KEY  — the anon public key
"""

import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_supabase: Client | None = None


def get_client() -> Client | None:
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
    """Grouped by type — kept for the AI summary's vitals string."""
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
                grouped[vt].append(
                    {
                        "reading": row["reading"],
                        "unit": row.get("unit", ""),
                        "recorded_at": row["recorded_at"],
                    }
                )
        return grouped
    except Exception as e:
        print(f"get_last_vitals error: {e}")
        return {}


def build_vitals_table(patient_id, max_dates=5):
    """
    Reshape vitals into a table:
      { "columns": ["Heart Rate", "Blood Pressure", ...],
        "rows": [ { "date": "2026-07-20", "values": {"Heart Rate": "72 bpm", ...} }, ... ] }
    Rows are newest date first. Missing readings simply aren't in `values`
    (the template renders a dash).
    """
    sb = get_client()
    if not sb:
        return {"columns": [], "rows": []}
    try:
        resp = (
            sb.table("vitals")
            .select("*")
            .eq("patient_id", patient_id)
            .order("recorded_at", desc=True)
            .execute()
        )
        rows = resp.data or []

        # Preserve column order by first appearance
        columns = []
        by_date = {}
        for r in rows:
            vt = r["vital_type"]
            if vt not in columns:
                columns.append(vt)
            date = r["recorded_at"]
            by_date.setdefault(date, {})
            # keep the first (newest) reading seen per (date, type)
            if vt not in by_date[date]:
                val = r["reading"]
                unit = r.get("unit", "")
                by_date[date][vt] = f"{val} {unit}".strip()

        # Sort dates newest first, cap to max_dates
        sorted_dates = sorted(by_date.keys(), reverse=True)[:max_dates]
        table_rows = [{"date": d, "values": by_date[d]} for d in sorted_dates]

        return {"columns": columns, "rows": table_rows}
    except Exception as e:
        print(f"build_vitals_table error: {e}")
        return {"columns": [], "rows": []}


def get_clinical_notes(patient_id, limit=5):
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
    sb = get_client()
    if not sb:
        return None
    try:
        resp = sb.table("patients").select("*").eq("id", patient_id).limit(1).execute()
        if not resp.data:
            return None
        patient = resp.data[0]
        patient["conditions"] = patient.get("conditions") or []
        patient["medications"] = patient.get("medications") or []
        patient["doctor"] = get_doctor(patient.get("assigned_doctor_id"))
        patient["vitals_grouped"] = get_last_vitals(patient_id, 3)  # for AI summary
        patient["vitals_table"] = build_vitals_table(patient_id, 5)  # for the UI table
        patient["notes"] = get_clinical_notes(patient_id, 5)
        return patient
    except Exception as e:
        print(f"get_patient_full error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  WRITE
# ══════════════════════════════════════════════════════════════════


def save_handoff_note(
    patient_id, note_content, ai_summary, priority_level, risk_keywords, doctor_username
):
    sb = get_client()
    if not sb:
        return None
    try:
        resp = (
            sb.table("handoff_notes")
            .insert(
                {
                    "patient_id": patient_id,
                    "note_content": note_content,
                    "ai_summary": ai_summary,
                    "priority_level": priority_level,
                    "risk_keywords": risk_keywords,
                    "doctor_username": doctor_username,
                }
            )
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"save_handoff_note error: {e}")
        return None


def save_priority_override(
    patient_id, system_priority, override_priority, reason, doctor_username
):
    """Record a clinician's priority override + reason (feedback capture)."""
    sb = get_client()
    if not sb:
        return None
    try:
        resp = (
            sb.table("priority_overrides")
            .insert(
                {
                    "patient_id": patient_id,
                    "system_priority": system_priority,
                    "override_priority": override_priority,
                    "reason": reason,
                    "doctor_username": doctor_username,
                }
            )
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"save_priority_override error: {e}")
        return None


def get_latest_override(patient_id):
    """Return the most recent clinician priority override for a patient, or None."""
    sb = get_client()
    if not sb:
        return None
    try:
        resp = (
            sb.table("priority_overrides")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"get_latest_override error: {e}")
        return None


def get_notes_text_by_patient():
    """One query -> {patient_id: 'all note text concatenated'}.

    Used to compute each patient's priority for the search list without
    firing a separate query per patient.
    """
    sb = get_client()
    if not sb:
        return {}
    try:
        resp = sb.table("clinical_notes").select("patient_id, content").execute()
        grouped = {}
        for r in resp.data or []:
            pid = r.get("patient_id")
            grouped.setdefault(pid, []).append(r.get("content", "") or "")
        return {pid: " ".join(texts) for pid, texts in grouped.items()}
    except Exception as e:
        print(f"get_notes_text_by_patient error: {e}")
        return {}


def get_latest_handoff(patient_id):
    """Return the most recent saved handoff note for a patient (or None).

    Used to show the Clinical Summary the instant the page loads, without
    calling the AI again — the summary was already generated and stored
    when the note was submitted.
    """
    sb = get_client()
    if not sb:
        return None
    try:
        resp = (
            sb.table("handoff_notes")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"get_latest_handoff error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  ADMIN STATS
# ══════════════════════════════════════════════════════════════════


def _display_name(username):
    """Turn a login username into a presentable name for the dashboard."""
    mapping = {
        "dr.sharma": "Dr. Sharma",
        "dr.mehta": "Dr. Mehta",
        "admin": "Admin",
    }
    if not username:
        return "—"
    if username in mapping:
        return mapping[username]
    # Fallback: 'dr.foo' -> 'Dr. Foo', otherwise Title Case
    parts = username.replace(".", " ").split()
    return " ".join(p.capitalize() for p in parts)


def get_admin_stats():
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
        pats = get_all_patients()
        name_by_id = {p["id"]: p["name"] for p in pats}

        total = len(notes)
        failed = sum(1 for n in notes if not n.get("ai_summary"))
        generated = total - failed

        activity = []
        for n in notes[:12]:
            created = n.get("created_at", "")
            ts = created.replace("T", "  ")[:16] if created else ""
            activity.append(
                {
                    "timestamp": ts,
                    "doctor": _display_name(n.get("doctor_username", "")),
                    "patient": name_by_id.get(
                        n.get("patient_id"), n.get("patient_id", "—")
                    ),
                    "action": "Generated Summary"
                    if n.get("ai_summary")
                    else "Summary Failed",
                    "priority": n.get("priority_level", ""),
                }
            )

        daily = {}
        for n in notes:
            created = n.get("created_at", "")
            day = created[:10] if created else "unknown"
            daily[day] = daily.get(day, 0) + 1
        daily_sorted = sorted(daily.items())[-7:]
        _months = [
            "",
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        def _fmt_day(d):  # d like "2026-08-19" -> "Aug 19"
            try:
                p = d.split("-")
                return f"{_months[int(p[1])]} {int(p[2])}"
            except Exception:
                return d[5:]

        daily_summaries = [{"date": _fmt_day(d), "count": c} for d, c in daily_sorted]

        pb = {}
        for n in notes:
            lvl = n.get("priority_level", "UNKNOWN") or "UNKNOWN"
            pb[lvl] = pb.get(lvl, 0) + 1

        return {
            "total_patients_viewed": total,
            "total_summaries_generated": generated,
            "total_failed_generations": failed,
            "activity_log": activity,
            "daily_summaries": daily_summaries,
            "priority_breakdown": pb,
        }
    except Exception as e:
        print(f"get_admin_stats error: {e}")
        return empty
