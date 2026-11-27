"""Explainable rule-based comparison. Labelled findings only; never an honesty/guilt score."""
import re

CONSISTENT = "Consistent with available evidence"
INCONSISTENT = "Potential inconsistency"
INSUFFICIENT = "Insufficient evidence"
UNVERIFIED = "Unverified"
REVIEW = "Requires human review"


def minutes(t):
    if not t:
        return None
    h, m = t.split(":")[:2]
    return int(h) * 60 + int(m)


def _tokens(s):
    return {w for w in re.findall(r"[a-z]+", (s or "").lower()) if w not in {"the", "a", "my", "of"}}


def same_place(a, b):
    return bool(_tokens(a) & _tokens(b))


def compare(claims, events, window_min=30):
    """Statement-sourced events are excluded: a statement is not independent evidence."""
    independent = [e for e in events if e.get("source_type") != "statement"]
    findings = []
    for c in claims:
        ct = minutes(c.get("claimed_time"))
        base = {"claim_id": c.get("id"), "claim_text": c["event_description"],
                "claim_source": c.get("source_reference"), "human_review_status": "pending"}
        if ct is None:
            findings.append({**base, "label": UNVERIFIED, "evidence": [],
                             "reason": "The claim has no explicit time, so it cannot be matched to dated evidence.",
                             "missing_verification": "A claimed time (ideally date and location)."})
            continue
        cands = []
        for e in independent:
            et = minutes(e.get("time"))
            if et is None:
                continue
            if c.get("claimed_date") and e.get("date") and c["claimed_date"] != e["date"]:
                continue
            if abs(et - ct) <= window_min:
                cands.append((abs(et - ct), e))
        if not cands:
            findings.append({**base, "label": INSUFFICIENT, "evidence": [],
                             "reason": f"No independent evidence record is within {window_min} minutes of the claimed time.",
                             "missing_verification": "Evidence covering the claimed time and place (footage, logs, documents)."})
            continue
        for diff, e in sorted(cands, key=lambda x: x[0]):
            ref = {k: e.get(k) for k in ("description", "source_type", "source_file", "source_ref", "date", "time", "location")}
            ref["event_id"] = e.get("id")
            cl, el = c.get("claimed_location"), e.get("location")
            if cl and el and same_place(cl, el):
                label = CONSISTENT
                why = f"A record {diff} min from the claimed time is at a matching location ('{el}')."
                miss = "Independent confirmation of which persons are involved."
            elif cl and el:
                label = INCONSISTENT
                why = (f"The claim places the speaker at '{cl}' around {c['claimed_time']}; a record {diff} min away "
                       f"is at '{el}'. Possible causes include a different person, a wrong timestamp or a clock offset.")
                miss = "Identity verification, device-clock verification, travel-time feasibility."
            else:
                label = REVIEW
                why = "A record exists near the claimed time but location is missing on the claim or the record."
                miss = "Location for the " + ("claim" if not cl else "evidence record") + "."
            findings.append({**base, "label": label, "evidence": [ref], "reason": why, "missing_verification": miss})
    return findings
