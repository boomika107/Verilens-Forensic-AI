from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors

DISCLAIMER = ("This report is an AI-assisted analysis of supplied information. It is not a determination of guilt, "
              "deception, identity or legal admissibility. All findings require independent verification by qualified human reviewers.")


def build_report(case, evidence, claims, events, timeline, findings, notes="", synthetic=False):
    ss = getSampleStyleSheet()
    P = lambda t, s="BodyText": Paragraph(escape(str(t)), ss[s])
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, title=f"VERILENS report {case['case_id']}")
    s = [P("VERILENS FORENSIC AI", "Title"), P("Multimodal Forensic Evidence Intelligence Platform"),
         Spacer(1, 8), P(DISCLAIMER, "Italic")]
    if synthetic:
        s.append(P("NOTE: this case contains clearly labelled SYNTHETIC demonstration data, not real evidence.", "Heading3"))

    def table(rows, head, widths=None):
        data = [head] + (rows or [["(none)"] + [""] * (len(head) - 1)])
        data = [[Paragraph(escape(str(c or "")), ss["BodyText"]) for c in r] for r in data]
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    s += [P("1. Case information", "Heading2"),
          table([[case["case_id"], case["title"], case.get("category"), case["status"], case["created"]]],
                ["Case ID", "Title", "Category", "Status", "Created"]),
          P("2. Evidence inventory and integrity", "Heading2"),
          P("SHA-256 values were recorded at upload. A matching hash indicates the stored bytes are unchanged relative to the "
            "recorded value; it does not prove the evidence is authentic."),
          table([[e["filename"], e["kind"], e["sha256"], e.get("integrity", "not checked")] for e in evidence],
                ["File", "Type", "SHA-256 (recorded)", "Last integrity check"], [110, 50, 210, 90]),
          P("3. Statement claims", "Heading2"),
          table([[c["event_description"], c.get("claimed_time"), c.get("claimed_date"), c.get("claimed_location"), c.get("source_reference")] for c in claims],
                ["Claim", "Time", "Date", "Location", "Source"]),
          P("4. Reconstructed timeline", "Heading2"),
          table([[e.get("date"), e.get("time"), e["description"], e.get("source_type"), f'{e.get("source_file") or ""} {e.get("source_ref") or ""}', e.get("human_review_status")] for e in timeline["ordered"]],
                ["Date", "Time", "Event", "Source", "Reference", "Review"], [50, 40, 170, 50, 100, 50]),
          P(f"Events with no usable timestamp (not placed on the timeline): {len(timeline['unplaced'])}"),
          P("5. Potential inconsistencies and comparison findings", "Heading2")]
    for f in findings:
        ev = "; ".join(f"{x.get('source_file')} @ {x.get('source_ref')} ({x.get('time')}, {x.get('location')})" for x in f["evidence"]) or "none"
        s += [P(f"[{f['label']}] Claim: {f['claim_text']}", "Heading4"), P(f"Evidence: {ev}"), P(f"Reason: {f['reason']}"),
              P(f"Missing verification: {f['missing_verification']}"), P(f"Human review: {f['human_review_status']}"), Spacer(1, 6)]
    s += [P("6. Limitations and uncertainty", "Heading2"),
          P("Object detection confidence is the detector's output only and is not the probability that any statement is true. "
            "Detections do not establish identity. Transcripts may contain errors. Dates/times are extracted by rules and may be wrong. "
            "No guilt, honesty or deception score is produced."),
          P("7. Human verification requirements", "Heading2"),
          P("Every finding above is pending or requires reviewer sign-off before being relied upon."),
          P("8. Investigator notes", "Heading2"), P(notes or "(none)"),
          P(f"Report generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"), Spacer(1, 10), P(DISCLAIMER, "Italic")]
    doc.build(s)
    return out.getvalue()
