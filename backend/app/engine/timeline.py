def build_timeline(events):
    """Sort by (date, time). Events without date/time are returned separately; timestamps are never invented."""
    dated = [e for e in events if e.get("time") or e.get("date")]
    undated = [e for e in events if not (e.get("time") or e.get("date"))]
    key = lambda e: (e.get("date") or "9999-99-99", e.get("time") or "99:99")
    return {"ordered": sorted(dated, key=key), "unplaced": undated}


def fmt_seconds(s):
    s = int(s)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
