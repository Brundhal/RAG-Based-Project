import os
import sys
import importlib

sys.path.insert(0, os.getcwd())
app = importlib.import_module("app")


chapter_text = (
    "Photosynthesis is the process by which green plants make food using sunlight, carbon dioxide, and water. "
    "Chlorophyll absorbs light energy. The process produces glucose and oxygen. "
    "Respiration is different because it releases energy from food."
)


pdf_data = [{
    "name": "chapter1.pdf",
    "page_texts": [chapter_text],
    "text": chapter_text,
    "raw_text": chapter_text,
    "page_count": 1,
    "has_text": True,
}]


search_index = app.build_search_index(pdf_data)
print("Built search index with", len(search_index["chunks"]), "chunks")

questions = [
    "What is photosynthesis?",
    "Difference between photosynthesis and respiration",
    "Summarize this chapter",
]

for question in questions:
    answer = app.answer_from_chunks(question, search_index, pdf_data)
    print("\nQuestion:", question)
    print("Answer:", answer)
