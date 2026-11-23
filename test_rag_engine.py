
from rag_engine import build_rag_index, retrieve_chunks, generate_answer

pages = [
    {
        "document": "sample.pdf",
        "page": 1,
        "text": (
            "Retrieval-Augmented Generation (RAG) combines "
            "information retrieval with text generation. "
            "It retrieves relevant information from documents "
            "and uses that information to generate answers."
        )
    }
]

print("Building FAISS index...")
rag_data = build_rag_index(pages)

print("Searching relevant information...")
results = retrieve_chunks(
    "What is Retrieval-Augmented Generation?",
    rag_data
)

print("Retrieved chunks:", len(results))

print("\nGenerating answer using Qwen...")
answer = generate_answer(
    "What is Retrieval-Augmented Generation?",
    results
)

print("\nANSWER:")
print(answer)
