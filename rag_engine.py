"""Hybrid semantic + lexical retrieval and grounded local answer generation."""
import re
import requests
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "qwen2.5:1.5b"
OLLAMA_URL = "http://localhost:11434/api/generate"
_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def create_chunks(pages, chunk_size=1200, overlap=200):
    """Create page-aware chunks; preserve headings and page citations."""
    chunks = []
    for page_data in pages:
        text = (page_data.get("text") or "").strip()
        if not text:
            continue
        document = page_data.get("document", "Unknown document")
        page_number = page_data.get("page", 1)
        # Prefer paragraph/line boundaries over cutting in the middle of a line.
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                if boundary > start + int(chunk_size * 0.65):
                    end = boundary + 1
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({"text": chunk_text, "document": document, "page": page_number})
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks


def build_rag_index(pages):
    chunks = create_chunks(pages)
    if not chunks:
        raise ValueError("No readable text found in the uploaded PDFs.")
    embedder = get_embedder()
    texts = [c["text"] for c in chunks]
    vectors = embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    vectors = np.asarray(vectors, dtype="float32")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return {"index": index, "chunks": chunks, "embedder": embedder}


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def retrieve_chunks(query, rag_data, top_k=8):
    """Retrieve candidates semantically, then rerank with lexical overlap."""
    if not query or not query.strip() or not rag_data or not rag_data.get("chunks"):
        return []
    chunks = rag_data["chunks"]
    qv = rag_data["embedder"].encode([query], convert_to_numpy=True, normalize_embeddings=True)
    qv = np.asarray(qv, dtype="float32")
    candidate_count = min(max(top_k * 4, 20), len(chunks))
    scores, indices = rag_data["index"].search(qv, candidate_count)
    qtokens = _tokens(query)
    ranked = []
    for semantic, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        chunk = chunks[int(idx)].copy()
        ctokens = _tokens(chunk["text"])
        lexical = len(qtokens & ctokens) / max(len(qtokens), 1)
        # Semantic similarity is primary; lexical overlap improves exact section queries.
        combined = 0.72 * float(semantic) + 0.28 * lexical
        chunk["score"] = combined
        chunk["semantic_score"] = float(semantic)
        chunk["lexical_score"] = lexical
        ranked.append(chunk)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]



def generate_answer(query, retrieved_chunks):
    if not retrieved_chunks:
        return "I couldn't find this information in the uploaded PDFs."

    context = "\n\n".join(
        f"[Document: {c['document']} | Page: {c['page']}]\n{c['text']}"
        for c in retrieved_chunks
    )

    prompt = f"""You are a helpful PDF question-answering assistant.

Answer the user's question using ONLY the information in the supplied PDF context.

Instructions:
1. Give a clear, complete answer in simple English.
2. Include all relevant points found in the context.
3. Use numbered points when the question asks for objectives, advantages, features or steps.
4. Do not mix unrelated sections.
5. Do not invent information or use outside knowledge.
6. If the answer is not available in the context, say:
"I couldn't find this information in the uploaded PDFs."
7. Always finish your sentences properly.

PDF CONTEXT:
{context}

QUESTION:
{query}

COMPLETE ANSWER:
"""

    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.8,
            "num_predict": 350,
            "num_ctx": 8192,
            "repeat_penalty": 1.1
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=180
        )
        response.raise_for_status()

        answer = response.json().get("response", "").strip()

        if not answer:
            return "I couldn't generate an answer. Please try again."

        return answer

    except requests.exceptions.RequestException as error:
        return (
            "Could not connect to Ollama. "
            "Please check that Ollama is running. "
            f"Details: {error}"
        )
