"""Document / video / audio extraction. Heavy dependencies are imported lazily with clear errors."""
import csv
from .timeline import fmt_seconds


def extract_document(path, ext):
    """Returns {'pages': [{'ref': 'page 1', 'text': ...}], 'metadata': {...}, 'warnings': [...]}"""
    warnings, meta = [], {}
    if ext == ".txt":
        return {"pages": [{"ref": "text", "text": open(path, encoding="utf-8", errors="replace").read()}], "metadata": meta, "warnings": warnings}
    if ext == ".csv":
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            rows = [" | ".join(r) for r in csv.reader(f)]
        return {"pages": [{"ref": f"row {i+1}", "text": r} for i, r in enumerate(rows)], "metadata": meta, "warnings": warnings}
    if ext == ".docx":
        import docx
        d = docx.Document(path)
        cp = d.core_properties
        meta = {"author": cp.author, "created": str(cp.created) if cp.created else None}
        return {"pages": [{"ref": f"paragraph {i+1}", "text": p.text} for i, p in enumerate(d.paragraphs) if p.text.strip()], "metadata": meta, "warnings": warnings}
    if ext == ".pdf":
        try:
            import fitz
        except ImportError:
            raise RuntimeError("PyMuPDF is not installed (pip install pymupdf).")
        doc = fitz.open(path)
        meta = {k: v for k, v in (doc.metadata or {}).items() if v}
        pages = []
        for i, pg in enumerate(doc):
            txt = pg.get_text().strip()
            if not txt:
                warnings.append(f"page {i+1}: no text layer (scanned?). OCR requires Tesseract.")
            pages.append({"ref": f"page {i+1}", "text": txt})
        return {"pages": pages, "metadata": meta, "warnings": warnings}
    raise ValueError(f"Unsupported document type {ext}")


def analyze_video(path, sample_every_s=2.0, max_frames=200, frames_dir=None, use_yolo=True):
    """Extract frames with OpenCV; run YOLO if ultralytics + weights are available.
    Confidence is the detector's confidence only. No identity inference."""
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Video could not be opened/decoded.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    if fps <= 0:
        raise ValueError("Video reports no frame rate; timestamps cannot be computed.")
    model, note = None, "Object detection skipped (disabled)."
    if use_yolo:
        try:
            from ultralytics import YOLO
            model, note = YOLO("yolov8n.pt"), "YOLOv8n (COCO classes)"
        except Exception as e:  # missing package or weights download failure
            note = f"YOLO unavailable ({type(e).__name__}); frames extracted without detections."
    step = max(1, int(fps * sample_every_s))
    obs, idx, n = [], 0, 0
    while n < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            break
        ts = idx / fps
        saved = None
        if frames_dir:
            saved = f"{frames_dir}/frame_{n:05d}.jpg"
            cv2.imwrite(saved, frame)
        if model:
            res = model(frame, verbose=False)[0]
            for b in res.boxes:
                name = res.names[int(b.cls)]
                if name in {"person", "car", "bus", "motorcycle", "truck", "bicycle"}:
                    obs.append({"offset_s": ts, "timestamp": fmt_seconds(ts), "label": name,
                                "confidence": float(b.conf), "frame_path": saved, "model": "YOLOv8n"})
        n += 1
        idx += step
        if total and idx >= total:
            break
    cap.release()
    return {"duration_s": total / fps, "fps": fps, "frames_extracted": n, "observations": obs, "detector": note}


def transcribe_audio(path, model_size="small", language=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper is not installed (pip install faster-whisper).")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segs, info = model.transcribe(path, language=language)
    return {"language": info.language, "language_probability": info.language_probability, "model": f"faster-whisper/{model_size}",
            "segments": [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs]}
