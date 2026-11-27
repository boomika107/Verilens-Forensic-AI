"""Case-scoped retrieval using TF-IDF (scikit-learn). Index is built per case at query time, so no cross-case leakage."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def chunk(text, size=600, overlap=100):
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out


def retrieve(query, passages, k=4, min_score=0.05):
    """passages: [{'text','source_file','ref'}] belonging to ONE case. Returns top-k with citations."""
    chunks = [{**p, "text": c} for p in passages for c in chunk(p["text"]) if c.strip()]
    if not chunks:
        return []
    vec = TfidfVectorizer(stop_words="english").fit([c["text"] for c in chunks] + [query])
    sims = cosine_similarity(vec.transform([query]), vec.transform([c["text"] for c in chunks]))[0]
    ranked = sorted(zip(sims, chunks), key=lambda x: -x[0])[:k]
    return [{**c, "score": round(float(s), 3)} for s, c in ranked if s >= min_score]


def answer(query, passages, llm=None):
    hits = retrieve(query, passages)
    if not hits:
        return {"answer": "No relevant information was found in this case's evidence.", "citations": [], "provider": "none"}
    if llm:
        return {"answer": llm(query, hits), "citations": hits, "provider": "llm"}
    return {"answer": "AI provider not configured. Showing the most relevant evidence passages (no generated analysis):",
            "citations": hits, "provider": "retrieval-only"}
