# importing dependencies
import os
import re
from collections import Counter, defaultdict
from io import BytesIO
from math import log, sqrt
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components
from PyPDF2 import PdfReader

try:
    import pypdfium2 as pdfium
    import pytesseract
except ImportError:
    pdfium = None
    pytesseract = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None

from htmlTemplates import css, bot_template, user_template


STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "this",
    "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "what", "which",
    "who", "whom", "whose", "where", "when", "why", "how", "and", "or", "but", "in", "on", "at",
    "to", "for", "of", "with", "by", "from", "into", "about", "as", "than", "then", "there",
    "their", "them", "his", "her", "our", "your", "its", "if", "so", "such", "also", "tell",
    "me", "explain", "describe", "summarize", "summary",
}


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text):
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def content_words(text):
    return [
        token for token in tokenize(text)
        if token not in STOP_WORDS and len(token) > 1
    ]


def expand_query_terms(question):
    words = set(content_words(question))
    expansions = set(words)

    synonym_map = {
        "define": {"meaning", "definition"},
        "definition": {"meaning", "define"},
        "difference": {"compare", "comparison", "different"},
        "compare": {"difference", "different", "comparison"},
        "advantages": {"benefits", "pros", "uses"},
        "benefits": {"advantages", "pros", "uses"},
        "disadvantages": {"limitations", "drawbacks", "cons"},
        "importance": {"significance", "important", "significant"},
        "significance": {"importance", "important", "significant"},
        "important": {"importance", "significant", "significance"},
        "significant": {"importance", "important", "significance"},
        "role": {"function", "purpose"},
        "function": {"role", "purpose"},
        "purpose": {"role", "function"},
        "uses": {"applications", "benefits", "advantages"},
        "application": {"applications", "use", "uses"},
        "applications": {"application", "use", "uses"},
        "cause": {"reason", "because"},
        "reasons": {"cause", "because"},
        "types": {"kinds", "categories"},
        "steps": {"process", "procedure", "stages"},
        "process": {"steps", "procedure", "stages"},
    }

    for word in list(words):
        expansions.update(synonym_map.get(word, set()))

    return expansions


def html_escape(text):
    text = (text or "").replace("&", "&amp;")
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("\n", "<br>")


def format_file_size(size):
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}{unit}"
        value /= 1024


def split_into_points(text, max_points=4):
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    points = []
    seen = set()

    for sentence in sentences:
        sentence = clean_text(re.sub(r"^[-*]\s*", "", sentence))

        if len(sentence) < 25:
            continue

        lowered = sentence.lower()

        if lowered in seen:
            continue

        seen.add(lowered)
        points.append(sentence)

        if len(points) >= max_points:
            break

    if not points and clean_text(text):
        points = [clean_text(text)]

    return points


def build_systematic_response(
    main_answer,
    explanation=None,
    points=None,
    source=None,
    confidence=None
):
    clean_points = [
        point for point in (points or [])
        if clean_text(point)
    ]
    answer_text = clean_text(main_answer)
    introductory_answer = re.match(
        r"^(?:here\s+(?:is|are)\b|i\s+(?:read|looked|pulled|found)\b)",
        answer_text,
        re.IGNORECASE,
    )
    sections = ["<div class='answer-format'>"]

    if answer_text and not (clean_points and introductory_answer):
        sections.append(
            "<p class='answer-text'>"
            f"{html_escape(answer_text)}"
            "</p>"
        )

    if clean_points:
        bullet_items = "".join(
            f"<li>{html_escape(point)}</li>"
            for point in clean_points
        )

        sections.append(f"<ul class='answer-list'>{bullet_items}</ul>")

    if source:
        sections.append(
            "<p class='answer-source'><strong>Source:</strong> "
            f"{html_escape(source)}"
            "</p>"
        )

    sections.append("</div>")

    return "".join(sections)


def split_into_sentences(text):
    return [
        clean_text(sentence)
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            clean_text(text)
        )
        if clean_text(sentence)
    ]


def split_into_paragraphs(text):
    raw_paragraphs = re.split(r"\n\s*\n|\n", text or "")

    paragraphs = [
        clean_text(paragraph)
        for paragraph in raw_paragraphs
        if clean_text(paragraph)
    ]

    if paragraphs:
        return paragraphs

    return [clean_text(text)] if clean_text(text) else []


def is_probable_noise_line(line):
    cleaned = clean_text(line)

    if not cleaned:
        return True

    lowered = cleaned.lower()

    if re.fullmatch(r"(page\s*)?\d+(\s*(of|/)\s*\d+)?", lowered):
        return True

    if re.fullmatch(r"chapter\s+\d+", lowered):
        return True

    if re.fullmatch(r"[ivxlcdm]+", lowered):
        return True

    if len(cleaned) <= 2:
        return True

    if len(re.findall(r"\d", cleaned)) > max(6, len(cleaned) * 0.45):
        return True

    if re.search(
        r"(all rights reserved|copyright|www\.|http|@\w+|isbn|published by)",
        lowered
    ):
        return True

    return False


def remove_headers_and_footers(page_texts):
    if not page_texts:
        return []

    normalized_pages = []

    for page_text in page_texts:
        raw_lines = [
            clean_text(line)
            for line in (page_text or "").splitlines()
        ]

        normalized_pages.append([
            line for line in raw_lines if line
        ])

    repeated_candidates = defaultdict(set)

    for page_index, lines in enumerate(normalized_pages):
        edge_lines = lines[:3] + lines[-3:]

        for line in edge_lines:
            normalized_line = re.sub(
                r"\d+", "<num>", line.lower()
            )

            if len(normalized_line) >= 4:
                repeated_candidates[normalized_line].add(page_index)

    repeated_noise = {
        candidate
        for candidate, pages in repeated_candidates.items()
        if len(pages) >= 2
    }

    cleaned_pages = []

    for lines in normalized_pages:
        cleaned_lines = []

        for idx, line in enumerate(lines):
            normalized_line = re.sub(
                r"\d+", "<num>", line.lower()
            )

            is_edge_line = (
                idx < 3 or idx >= max(len(lines) - 3, 0)
            )

            if is_edge_line and normalized_line in repeated_noise:
                continue

            if is_probable_noise_line(line):
                continue

            cleaned_lines.append(line)

        cleaned_pages.append("\n".join(cleaned_lines))

    return cleaned_pages


# extracting text from pdf
def get_pdf_text(docs):
    text = ""
    pdf_data = []

    for pdf in docs:
        pdf.seek(0)
        pdf_bytes = pdf.read()
        pdf.seek(0)
        pdf_reader = PdfReader(BytesIO(pdf_bytes))
        raw_pages = []

        for page in pdf_reader.pages:
            page_text = page.extract_text() or ""
            raw_pages.append(page_text)

        ocr_used = False

        if not any(page_text.strip() for page_text in raw_pages):
            if pdfium is None or pytesseract is None:
                raise RuntimeError(
                    "This PDF has no selectable text and needs OCR. "
                    "Install the packages in requirements-ocr.txt and install "
                    "Tesseract OCR with tesseract.exe available on PATH."
                )

            configured_tesseract = os.environ.get("TESSERACT_CMD")
            standard_tesseract_path = Path(
                r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            )
            if configured_tesseract:
                pytesseract.pytesseract.tesseract_cmd = configured_tesseract
            elif os.name == "nt" and standard_tesseract_path.is_file():
                pytesseract.pytesseract.tesseract_cmd = str(
                    standard_tesseract_path
                )

            try:
                pytesseract.get_tesseract_version()
            except pytesseract.TesseractNotFoundError as exc:
                raise RuntimeError(
                    "Tesseract OCR is not installed or is not available on PATH. "
                    "Install Tesseract OCR, then restart the app."
                ) from exc

            ocr_document = pdfium.PdfDocument(pdf_bytes)
            try:
                for page_number in range(len(ocr_document)):
                    page = ocr_document[page_number]
                    try:
                        bitmap = page.render(scale=3)
                        try:
                            raw_pages[page_number] = (
                                pytesseract.image_to_string(
                                    bitmap.to_pil(),
                                    lang="eng",
                                )
                            )
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
            finally:
                ocr_document.close()

            ocr_used = True

        cleaned_page_texts = remove_headers_and_footers(raw_pages)

        raw_pdf_text = "\n".join(raw_pages)
        cleaned_pdf_text = "\n".join(cleaned_page_texts)

        pdf_text = clean_text(cleaned_pdf_text)

        text += pdf_text + "\n"

        pdf_data.append({
            "name": pdf.name,
            "page_texts": [
                "\n".join(
                    clean_text(line)
                    for line in page_text.splitlines()
                    if clean_text(line)
                )
                for page_text in cleaned_page_texts
            ],
            "raw_text": raw_pdf_text,
            "text": pdf_text,
            "page_count": len(pdf_reader.pages),
            "has_text": bool(pdf_text),
            "ocr_used": ocr_used,
        })

    return clean_text(text), pdf_data


def get_chunks(raw_text, chunk_size=900, chunk_overlap=180):
    paragraphs = split_into_paragraphs(raw_text)

    if not paragraphs:
        return []

    chunks = []
    current = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph = clean_text(paragraph)

        if not paragraph:
            continue

        if len(paragraph) > chunk_size:
            sentences = split_into_sentences(paragraph)
            buffer = ""

            for sentence in sentences:
                if len(buffer) + len(sentence) + 1 <= chunk_size:
                    buffer = f"{buffer} {sentence}".strip()
                else:
                    if buffer:
                        chunks.append(buffer)

                    buffer = sentence

            if buffer:
                chunks.append(buffer)

            continue

        if current and current_length + len(paragraph) + 1 > chunk_size:
            chunk_text = " ".join(current).strip()

            if chunk_text:
                chunks.append(chunk_text)

            overlap_text = (
                chunk_text[-chunk_overlap:]
                if chunk_overlap > 0 else ""
            )

            current = (
                [clean_text(overlap_text), paragraph]
                if overlap_text else [paragraph]
            )

            current = [item for item in current if item]
            current_length = len(" ".join(current))

        else:
            current.append(paragraph)
            current_length += len(paragraph) + 1

    if current:
        chunks.append(" ".join(current).strip())

    return [
        clean_text(chunk)
        for chunk in chunks
        if clean_text(chunk)
    ]


def build_search_index(pdf_data):
    chunks = []

    for pdf in pdf_data:
        page_texts = pdf.get("page_texts", [])

        if page_texts:
            for page_number, page_text in enumerate(
                page_texts, start=1
            ):
                for chunk_position, chunk in enumerate(
                    get_chunks(page_text), start=1
                ):
                    chunks.append({
                        "document": pdf.get("name", "PDF"),
                        "page": page_number,
                        "text": chunk,
                        "chunk_position": chunk_position,
                        "content_words": set(content_words(chunk)),
                        "score": 0.0,
                    })

        else:
            for chunk_position, chunk in enumerate(
                get_chunks(pdf.get("text", "")), start=1
            ):
                chunks.append({
                    "document": pdf.get("name", "PDF"),
                    "page": None,
                    "text": chunk,
                    "chunk_position": chunk_position,
                    "content_words": set(content_words(chunk)),
                    "score": 0.0,
                })

    if not chunks:
        return {
            "chunks": [],
            "vectorizer": None,
            "matrix": None,
            "char_vectorizer": None,
            "char_matrix": None,
            "neighbors": {},
        }

    neighbors = {}
    grouped_chunks = defaultdict(list)

    for index, chunk in enumerate(chunks):
        grouped_chunks[
            (chunk["document"], chunk["page"])
        ].append((index, chunk))

    for group_items in grouped_chunks.values():
        indexes = [
            index
            for index, _ in sorted(
                group_items,
                key=lambda item: item[1]["chunk_position"]
            )
        ]

        for position, chunk_index in enumerate(indexes):
            nearby = []

            if position > 0:
                nearby.append(indexes[position - 1])

            if position + 1 < len(indexes):
                nearby.append(indexes[position + 1])

            neighbors[chunk_index] = nearby

    if TfidfVectorizer:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
        )

        matrix = vectorizer.fit_transform([
            chunk["text"] for chunk in chunks
        ])

        char_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            sublinear_tf=True
        )

        char_matrix = char_vectorizer.fit_transform([
            chunk["text"] for chunk in chunks
        ])

        return {
            "chunks": chunks,
            "vectorizer": vectorizer,
            "matrix": matrix,
            "char_vectorizer": char_vectorizer,
            "char_matrix": char_matrix,
            "neighbors": neighbors,
        }

    return {
        "chunks": chunks,
        "vectorizer": None,
        "matrix": None,
        "char_vectorizer": None,
        "char_matrix": None,
        "neighbors": neighbors,
    }


def retrieve_chunks(question, search_index, limit=6):
    """Find relevant PDF chunks using multiple similarity methods."""
    chunks = search_index.get("chunks", [])

    if not chunks:
        return []

    query_terms = expand_query_terms(question)

    vectorizer = search_index.get("vectorizer")
    matrix = search_index.get("matrix")
    char_vectorizer = search_index.get("char_vectorizer")
    char_matrix = search_index.get("char_matrix")

    scored = []

    if vectorizer is not None and matrix is not None and cosine_similarity:
        query_vector = vectorizer.transform([question])
        word_scores = cosine_similarity(
            query_vector, matrix
        ).flatten()

        char_scores = None

        if char_vectorizer is not None and char_matrix is not None:
            char_query_vector = char_vectorizer.transform([question])
            char_scores = cosine_similarity(
                char_query_vector, char_matrix
            ).flatten()

        for index, chunk in enumerate(chunks):
            chunk_words = chunk.get("content_words", set())

            overlap_score = (
                len(query_terms & chunk_words)
                / max(len(query_terms), 1)
            )

            word_score = float(word_scores[index])

            char_score = (
                float(char_scores[index])
                if char_scores is not None else 0.0
            )

            exact_phrase_bonus = (
                0.10
                if clean_text(question).lower() in chunk["text"].lower()
                else 0.0
            )

            final_score = (
                0.55 * word_score
                + 0.15 * char_score
                + 0.30 * overlap_score
                + exact_phrase_bonus
            )

            scored.append((final_score, index))

    else:
        for index, chunk in enumerate(chunks):
            chunk_words = chunk.get(
                "content_words",
                set(content_words(chunk["text"]))
            )

            overlap_score = (
                len(query_terms & chunk_words)
                / max(len(query_terms), 1)
            )

            if overlap_score > 0:
                scored.append((overlap_score, index))

    scored.sort(key=lambda item: item[0], reverse=True)

    if not scored:
        return []

    best_score = scored[0][0]

    # Reject weak matches rather than presenting unrelated text.
    if best_score < 0.08:
        return []

    results = []

    for score, index in scored:
        if len(results) >= limit:
            break

        if score < best_score * 0.35:
            continue

        chunk = dict(chunks[index])
        chunk["score"] = float(score)
        results.append(chunk)

    return results


def summarize_text(raw_text, max_sentences=6):
    sentences = []
    seen = set()
    for sentence in split_into_sentences(raw_text):
        normalized = sentence.lower()
        words = re.findall(r"[A-Za-z]+", sentence)
        uppercase_ratio = (
            sum(word.isupper() for word in words) / len(words)
            if words else 0
        )
        if (
            len(sentence) > 35
            and len(sentence) <= 400
            and sentence.count(";") <= 2
            and normalized not in seen
            and uppercase_ratio < 0.05
        ):
            sentences.append(sentence)
            seen.add(normalized)

    if not sentences:
        return (
            "The uploaded PDF was processed, but it does not "
            "contain enough readable text to summarize."
        )

    sentence_words = [
        set(content_words(sentence))
        for sentence in sentences
    ]
    document_frequency = Counter(
        word for words in sentence_words for word in words
    )
    sentence_scores = []

    for index, words in enumerate(sentence_words):
        if not words:
            continue

        score = sum(
            log((len(sentences) + 1) / (document_frequency[word] + 1)) + 1
            for word in words
        ) / sqrt(len(words))
        score /= sqrt(1 + index / 20)

        if not re.search(r"[.!?]", sentences[index]):
            score *= 0.7

        sentence_scores.append((score, index))

    ranked_sentences = sorted(sentence_scores, reverse=True)
    selected_indexes = {
        index for _, index in ranked_sentences[:max_sentences]
    }
    if sentence_scores and max_sentences > 0:
        lead_index = min(index for _, index in sentence_scores)
        selected_indexes.add(lead_index)
        if len(selected_indexes) > max_sentences:
            scores_by_index = {
                index: score for score, index in sentence_scores
            }
            lowest_ranked_selected = min(
                (index for index in selected_indexes if index != lead_index),
                key=scores_by_index.get,
            )
            selected_indexes.remove(lowest_ranked_selected)

    return "\n".join(
        f"- {sentence}"
        for index, sentence in enumerate(sentences)
        if index in selected_indexes
    )


def extract_candidate_name(pdf_data):
    lines = []

    for pdf in pdf_data or []:
        raw_text = pdf.get("raw_text") or pdf.get("text", "")
        lines.extend(
            clean_text(line)
            for line in raw_text.splitlines()
        )

    skip_terms = {
        "resume", "cv", "curriculum", "vitae", "email",
        "phone", "mobile", "address", "education",
        "experience", "skills", "project", "projects",
        "profile", "summary", "objective", "linkedin",
        "github",
    }

    for line in lines[:20]:
        if not line:
            continue

        if any(term in line.lower() for term in skip_terms):
            continue

        if re.search(r"[@\d]", line):
            continue

        words = line.split()

        if (
            2 <= len(words) <= 4
            and all(
                re.fullmatch(r"[A-Z][A-Za-z.'-]*", word)
                for word in words
            )
        ):
            return line

    for pdf in pdf_data or []:
        stem = Path(pdf.get("name", "")).stem
        filename_match = re.match(
            r"^([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,2})"
            r"(?=_|\s+(?:resume|cv)\b)",
            stem,
            re.IGNORECASE,
        )
        if filename_match:
            candidate = filename_match.group(1).strip()
            if not any(
                word.lower() in skip_terms
                for word in candidate.split()
            ):
                return candidate

    return None


def extract_education_detail(pdf_data, keywords):
    lines = []

    for pdf in pdf_data or []:
        raw_text = pdf.get("raw_text") or pdf.get("text", "")

        lines.extend(
            clean_text(line)
            for line in raw_text.splitlines()
        )

    for line in lines:
        lower_line = line.lower()

        if any(keyword in lower_line for keyword in keywords):
            return line

    combined_text = " ".join(
        pdf.get("text", "")
        for pdf in pdf_data or []
    )

    pattern = re.compile(
        rf"([^\.\n]{{0,80}}(?:{'|'.join(re.escape(keyword) for keyword in keywords)})[^\.\n]{{0,120}})",
        re.IGNORECASE
    )

    match = pattern.search(combined_text)

    return clean_text(match.group(1)) if match else None


def extract_page_number(question):
    ordinal_match = re.search(
        r"\b(\d+)(?:st|nd|rd|th)\s+page\b",
        question.lower()
    )

    if ordinal_match:
        return int(ordinal_match.group(1))

    page_match = re.search(
        r"\bpage\s+(\d+)\b",
        question.lower()
    )

    if page_match:
        return int(page_match.group(1))

    return None



def is_short_fact_question(question):
    """Identify short factual questions that should get a one-line answer."""
    q = clean_text(question).lower()
    if not q:
        return False

    detailed_intent = re.search(
        r"\b(explain|describe|elaborate|summari[sz]e|overview|tell me about|"
        r"tell about|what is this document about|why|how does|how do|steps|procedure|"
        r"compare|comparison|difference|list all|give details|in detail|"
        r"significance|importance|impact|effects|projects|skills|education|experience|qualifications|features|"
        r"components|advantages|disadvantages|types|applications)\b",
        q,
    )
    if detailed_intent:
        return False

    # Short prompts such as "CGPA?", "school name", "author?",
    # "date of publication?" are treated as factual lookups.
    words = content_words(q)
    return len(words) <= 7


def find_focused_fact_answer(question, pdf_data):
    """Find the smallest relevant source line/value across any uploaded PDF."""
    question_words = set(content_words(question))
    if not question_words:
        return None, None

    def comparable_words(words):
        comparable = set(words)
        for word in words:
            if len(word) > 4 and word.endswith("ies"):
                comparable.add(word[:-3] + "y")
            elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
                comparable.add(word[:-1])
        return comparable

    question_words = comparable_words(question_words)
    definition_question = bool(
        re.search(r"\b(?:what\s+is|define|definition\s+of)\b", question, re.I)
    )
    candidates = []
    for pdf in pdf_data or []:
        document_name = pdf.get("name", "PDF")
        raw_text = pdf.get("raw_text", "") or ""
        page_texts = pdf.get("page_texts") or [raw_text]
        has_page_texts = bool(pdf.get("page_texts"))

        for page_number, page_text in enumerate(page_texts, start=1):
            lines = [
                clean_text(line)
                for line in (page_text or "").splitlines()
            ]
            for line_number, line in enumerate(lines, start=1):
                if len(line) < 25:
                    continue
                line_words = comparable_words(set(content_words(line)))
                if not re.search(
                    r"\b(is|are|was|were|means|refers|defined|called|includes|"
                    r"contains|has|have|developed|designed|studied|earned|"
                    r"obtained)\b|[.!?;:•]",
                    line,
                    re.IGNORECASE,
                ):
                    continue
                overlap = question_words & line_words
                if not overlap:
                    continue

                coverage = len(overlap) / max(len(question_words), 1)
                compactness = 1.0 / (1.0 + max(len(line) - 100, 0) / 100)
                definition_bonus = (
                    1.0
                    if definition_question and re.search(
                        r"\b(is|means|refers to|defined as)\b",
                        line,
                        re.IGNORECASE,
                    )
                    else 0.0
                )
                score = (coverage * 3.0) + compactness + definition_bonus
                candidates.append((
                    score,
                    line,
                    document_name,
                    page_number if has_page_texts else None,
                    line_number,
                ))

        # Generic label:value extraction is useful when a PDF extractor places
        # several fields on one physical line (e.g. "CGPA: 8.55/10 ...").
        for word in question_words:
            label_pattern = re.compile(
                rf"\b{re.escape(word)}\b(?:\s*[:：=]|\s+-\s+)"
                rf"\s*([^\n|;]+)",
                re.IGNORECASE,
            )
            for page_number, page_text in enumerate(page_texts, start=1):
                for match in label_pattern.finditer(page_text or ""):
                    value = clean_text(match.group(1))
                    if not value:
                        continue

                    if re.match(r"^[+-]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?%?", value):
                        numeric = re.match(
                            r"^[+-]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?%?",
                            value,
                        )
                        value = numeric.group(0).strip()
                    else:
                        value = re.split(
                            r"\s{2,}|\s+(?=[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\s*(?:20\d{2}|[:：]))",
                            value,
                            maxsplit=1,
                        )[0]
                        value = value[:140].strip(" .,:;-–")

                    if value:
                        candidates.append((
                            10.0,
                            f"{word.upper()}: {value}",
                            document_name,
                            page_number if has_page_texts else None,
                            None,
                        ))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: (item[0], -len(item[1])), reverse=True)
    _, answer, document_name, page_number, line_number = candidates[0]
    source = document_name
    if page_number is not None:
        source += f", page {page_number}"
    elif line_number is not None:
        source += f", extracted line {line_number}"
    return answer, source


def find_resume_project_entries(pdf_data):
    entries = []
    section_heading = re.compile(
        r"^(?:key\s+|personal\s+)?projects?\s*[:\-]?$",
        re.IGNORECASE,
    )
    next_section = re.compile(
        r"^(education|experience|skills|certifications?|achievements?|"
        r"activities|interests|summary|profile|objective)\b",
        re.IGNORECASE,
    )

    for pdf in pdf_data or []:
        in_project_section = False
        for page_number, page_text in enumerate(
            pdf.get("page_texts", []),
            start=1,
        ):
            for raw_line in (page_text or "").splitlines():
                line = clean_text(raw_line)
                if not line:
                    continue

                if section_heading.fullmatch(line.strip("•-* \t")):
                    in_project_section = True
                    continue

                if in_project_section and next_section.match(line):
                    in_project_section = False

                parts = re.split(r"\s*[•●▪]\s*", line, maxsplit=1)
                if len(parts) != 2 or not (in_project_section or re.search(
                    r"\b(project|website|application|analyzer|platform)\b",
                    line,
                    re.IGNORECASE,
                )):
                    continue

                title, description = (clean_text(part) for part in parts)
                if len(title) < 3 or len(description) < 15:
                    continue

                entry = f"{title}: {description}"
                if not any(existing[0].lower() == entry.lower() for existing in entries):
                    entries.append((
                        entry,
                        pdf.get("name", "PDF"),
                        page_number,
                    ))

    return entries

def is_summary_request(question):
    q = question.lower()

    summary_terms = re.search(
        r"\b(summary|summarize|overview|gist|brief)\b",
        q
    )

    document_terms = re.search(
        r"\b(document|pdf|chapter|file|text|content|whole)\b",
        q
    )

    broad_prompt = re.search(
        r"\bwhat\s+(?:is|are)\s+(?:this|the)\s+"
        r"(?:document|pdf|chapter|file|content|text)\s+about\b|"
        r"\b(?:give|provide)\s+me\s+(?:a\s+)?summary\b|"
        r"\bsummarize\s+(?:this|the)\s+"
        r"(?:document|pdf|chapter|file|content|text)\b",
        q
    )

    return bool(
        broad_prompt or (summary_terms and document_terms)
    )


def find_relevant_section_list(question, pdf_data):
    question_terms = expand_query_terms(question)
    original_terms = set(content_words(question))
    if not question_terms or not original_terms:
        return None

    candidates = []

    for pdf in pdf_data or []:
        for page_number, page_text in enumerate(
            pdf.get("page_texts", []),
            start=1,
        ):
            lines = [
                clean_text(line)
                for line in (page_text or "").splitlines()
            ]

            for heading_index, heading in enumerate(lines):
                if not heading or len(heading) > 120:
                    continue

                heading_terms = set(content_words(heading))
                overlap = question_terms & heading_terms
                coverage = min(
                    1.0,
                    len(overlap) / max(len(original_terms), 1),
                )
                if coverage < 0.5:
                    continue

                items = []
                current_item = None

                for line in lines[heading_index + 1:heading_index + 80]:
                    if not line:
                        continue

                    if re.match(r"^\d+(?:\.\d+)+\s+\S", line):
                        break

                    numbered_item = re.match(r"^\d+[.)]\s*(.+)", line)
                    if numbered_item:
                        if current_item:
                            items.append(clean_text(current_item))
                        current_item = numbered_item.group(1)
                    elif current_item:
                        current_item += " " + line
                    elif items:
                        items[-1] += " " + line

                    if len(items) >= 5:
                        break

                if current_item:
                    items.append(clean_text(current_item))

                items = [
                    item for item in items
                    if len(item) > 25
                ][:5]

                if len(items) >= 2:
                    candidates.append((
                        coverage - (len(heading) / 1000),
                        items,
                        pdf.get("name", "PDF"),
                        page_number,
                    ))

    if not candidates:
        return None

    _, items, document_name, page_number = max(
        candidates,
        key=lambda candidate: candidate[0],
    )
    return items, document_name, page_number


def format_sources(matches):
    sources = {}

    for match in matches:
        document = match.get("document", "PDF")
        page = match.get("page")

        sources.setdefault(document, set())

        if page is not None:
            sources[document].add(page)

    formatted = []

    for document in sorted(sources):
        pages = sorted(sources[document])

        if pages:
            formatted.append(
                f"{document}, page {', '.join(str(page) for page in pages)}"
            )
        else:
            formatted.append(document)

    return "; ".join(formatted)


def normalize_confidence(raw_score):
    if raw_score is None:
        return None

    score = max(0.0, min(float(raw_score), 1.0))

    if score < 0.10:
        percent = 20 + (score * 200)

    elif score < 0.25:
        percent = 40 + ((score - 0.10) * 200)

    else:
        percent = 70 + ((score - 0.25) * 38)

    return max(1, min(99, int(round(percent))))


def best_match_score(matches):
    if not matches:
        return 0.0

    return max(
        float(match.get("score", 0.0))
        for match in matches
    )


def get_conversational_reply(question):
    q = clean_text(question).lower()

    if not q:
        return None

    if re.fullmatch(
        r"(hi|hello|hey|hii|hiii|hola|good morning|good afternoon|good evening)",
        q
    ):
        return build_systematic_response(
            "Hello! I am ready to help you with your PDF.",
            "You can ask me to explain a topic, summarize a chapter, compare concepts, or find information from a page.",
            [
                "Ask simple questions in natural language.",
                "You can also use voice input if needed.",
                "Upload and process the PDF first for best results.",
            ],
            confidence=99,
        )

    if re.fullmatch(
        r"(thank you|thanks|thankyou|thx|thanks a lot|thank you so much)",
        q
    ):
        return build_systematic_response(
            "You are very welcome.",
            "I am happy to help. If you want, ask another question from the PDF and I will explain it in a simple way.",
            [
                "I can summarize chapters.",
                "I can explain answers step by step.",
                "I can also find page-wise information.",
            ],
            confidence=99,
        )

    if re.fullmatch(
        r"(bye|goodbye|see you|ok bye|bye bye)",
        q
    ):
        return build_systematic_response(
            "Goodbye and take care.",
            "Come back anytime if you want help with another PDF or another question.",
            confidence=99,
        )

    if re.fullmatch(
        r"(how are you|how are you doing|how r u)",
        q
    ):
        return build_systematic_response(
            "I am doing well and ready to help you.",
            "Please ask any question from your PDF, and I will answer it in a clear and simple format.",
            confidence=99,
        )

    return None


def extract_comparison_terms(question):
    patterns = [
        r"\bdifference between ([a-zA-Z0-9 \-]+?) and ([a-zA-Z0-9 \-]+?)(?:\?|$)",
        r"\bcompare ([a-zA-Z0-9 \-]+?) and ([a-zA-Z0-9 \-]+?)(?:\?|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, question.lower())

        if match:
            first = clean_text(match.group(1))
            second = clean_text(match.group(2))

            if first and second:
                return first, second

    return None


def sentence_score(sentence, question_terms, question_text):
    sentence_words = set(content_words(sentence))

    if not sentence_words or sentence.rstrip().endswith("?"):
        return 0

    if re.search(r"(?:^|\s)\d+\.\s*$", sentence):
        return 0

    overlap = len(question_terms & sentence_words)

    phrase_bonus = (
        2
        if clean_text(question_text).lower() in sentence.lower()
        else 0
    )

    starts_like_definition = (
        1
        if re.search(
            r"\b(is|refers to|means|defined as)\b",
            sentence.lower()
        )
        else 0
    )

    starts_with_topic = (
        3
        if any(
            sentence.lower().startswith(term.lower())
            for term in question_terms
            if len(term) > 3
        )
        else 0
    )

    length_bonus = min(len(sentence) / 180, 1.0)

    return (
        (overlap * 3)
        + phrase_bonus
        + starts_like_definition
        + starts_with_topic
        + length_bonus
    )


def find_best_sentence_for_term(term, matches):
    term_words = set(content_words(term))

    if not term_words:
        return None

    best = None

    for match in matches:
        for sentence in split_into_sentences(match["text"]):
            sentence_words = set(content_words(sentence))
            overlap = len(term_words & sentence_words)

            if overlap == 0:
                continue

            score = (
                (overlap * 3)
                + min(len(sentence) / 200, 1.0)
            )

            if best is None or score > best[0]:
                best = (score, sentence, match)

    return best


def select_best_sentences(question, matches, max_sentences=5):
    question_terms = expand_query_terms(question)
    candidates = []

    for match in matches:
        sentences = split_into_sentences(match["text"])

        for sentence in sentences:
            if sentence.rstrip().endswith("?"):
                continue

            score = sentence_score(
                sentence,
                question_terms,
                question
            )

            if score > 0:
                candidates.append((score, sentence, match))

    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    selected = []
    used_sentences = set()
    selected_matches = []

    for score, sentence, match in candidates:
        normalized = sentence.lower()

        if normalized in used_sentences:
            continue

        used_sentences.add(normalized)
        selected.append(sentence)
        selected_matches.append(match)

        if len(selected) >= max_sentences:
            break

    return selected, selected_matches
def render_voice_input():
    components.html(
        """
        <style>
        body { margin: 0; }
        #voice-control { align-items: center; display: flex; gap: 10px; height: 48px; }
        #voice-btn {
            align-items: center; background: #17466f; border: 2px solid #47769c; border-radius: 50%;
            box-shadow: 0 4px 12px rgba(0,0,0,.2); color: #fff; cursor: pointer; display: flex;
            flex: 0 0 48px; height: 48px; justify-content: center; padding: 0; position: relative;
            transition: background 150ms ease; width: 48px;
        }
        #voice-btn:hover { background: #103a5d; }
        #voice-btn:focus-visible { outline: 3px solid #8fc7ff; outline-offset: 2px; z-index: 1; }
        #voice-btn.recording { background: #c62828; border-color: #ffb4a9; }
        #voice-btn:disabled { cursor: not-allowed; opacity: 0.55; }
        #voice-status {
            background: #172033; border: 1px solid #8da7c0; border-radius: 8px; color: #fff;
            font: 600 13px/1.3 sans-serif; max-width: min(520px, calc(100vw - 90px));
            overflow-wrap: anywhere; padding: 7px 10px;
        }
        #recording-indicator {
            animation: pulse 1.15s ease-in-out infinite; background: #ff8585;
            border: 2px solid #fff; border-radius: 50%; display: none; height: 0.7rem;
            position: absolute; right: 0.5rem; top: 0.45rem; width: 0.7rem;
        }
        #voice-btn.recording #recording-indicator { display: block; }
        #mic-icon { fill: currentColor; height: 1.35rem; width: 1.35rem; }
        @keyframes pulse {
            50% { box-shadow: 0 0 0 5px rgba(255, 133, 133, 0.22); opacity: 0.75; }
        }
        @media (prefers-reduced-motion: reduce) { #recording-indicator { animation: none; } }
        </style>
        <div id="voice-control">
            <button id="voice-btn" type="button" aria-label="Start voice input" title="Start voice input" aria-pressed="false">
                <svg id="mic-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93V21h2v-3.07A7 7 0 0 0 19 11h-2Z"/>
                </svg>
                <span id="recording-indicator" aria-hidden="true"></span>
            </button>
            <span id="voice-status" role="status" aria-live="polite">Click the mic to speak</span>
        </div>
        <script>
        const button = document.getElementById("voice-btn");
        const status = document.getElementById("voice-status");
        const parentWindow = window.parent;
        const SpeechRecognition = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;
        const setStatus = function (message) {
            status.textContent = message;
            button.title = message;
        };
        const setListeningState = function (active) {
            button.classList.toggle("recording", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
            button.setAttribute("aria-label", active ? "Stop voice input" : "Start voice input");
            if (!active && status.textContent === "Listening... speak now") {
                setStatus("Click the mic to speak");
            }
        };
        const inputSelector = 'input[aria-label="Question"], input[aria-label="Ask question from your document:"]';

        if (!parentWindow.isSecureContext) {
            button.disabled = true;
            setStatus("Microphone blocked on this HTTP network address. Open localhost on this computer or use HTTPS.");
        } else if (!parentWindow.navigator.mediaDevices
            || !parentWindow.navigator.mediaDevices.getUserMedia) {
            button.disabled = true;
            setStatus("This browser does not provide microphone access. Check browser support and permissions.");
        } else if (!SpeechRecognition) {
            button.disabled = true;
            setStatus("Voice input is not supported in this browser. Use Chrome or Edge.");
        } else {
            const recognition = new SpeechRecognition();
            recognition.lang = "en-US";
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;
            let isListening = false;
            let startingText = "";
            let finalTranscript = "";
            let interimTranscript = "";
            let lastError = "";
            let stopTimer = null;
            let stopping = false;

            const updateQuestion = function (transcript, commit) {
                const input = parentWindow.document.querySelector(inputSelector)
                    || parentWindow.document.querySelector('[data-testid="stTextInput"] input');
                const valueSetter = Object.getOwnPropertyDescriptor(parentWindow.HTMLInputElement.prototype, "value");

                if (!input || !valueSetter || !valueSetter.set) return false;
                valueSetter.set.call(
                    input,
                    [startingText, transcript.trim()].filter(Boolean).join(startingText && transcript.trim() ? " " : "")
                );
                input.dispatchEvent(new parentWindow.Event("input", { bubbles: true }));
                if (commit) {
                    input.dispatchEvent(new parentWindow.Event("change", { bubbles: true }));
                }
                return true;
            };
            const getTranscript = function () {
                return (finalTranscript + interimTranscript).trim();
            };
            const commitTranscript = function () {
                const transcript = getTranscript();
                return transcript && updateQuestion(transcript, true) ? transcript : "";
            };

            recognition.onstart = function () {
                isListening = true;
                stopping = false;
                lastError = "";
                finalTranscript = "";
                interimTranscript = "";
                const input = parentWindow.document.querySelector(inputSelector);
                startingText = input ? input.value.trim() : "";
                setListeningState(true);
                setStatus("Listening... speak now");
            };

            recognition.onresult = function (event) {
                finalTranscript = "";
                interimTranscript = "";
                for (let index = 0; index < event.results.length; index += 1) {
                    const result = event.results[index];
                    const text = result[0].transcript || "";
                    if (result.isFinal) {
                        finalTranscript += text;
                    } else {
                        interimTranscript += text;
                    }
                }
                const transcript = getTranscript();
                if (!updateQuestion(transcript, false)) {
                    setStatus("Speech recognized, but the question box could not be found.");
                    return;
                }
                setStatus(transcript ? "Listening... " + transcript : "Listening... speak now");
            };

            recognition.onerror = function (event) {
                const messages = {
                    "not-allowed": "Microphone permission blocked. Allow microphone access in browser settings.",
                    "service-not-allowed": "Speech service blocked. Check browser permissions.",
                    "no-speech": "No speech was recognized. Check microphone access and try again.",
                    "audio-capture": "No microphone detected. Check your device.",
                    "network": "Speech service could not connect. Check your internet connection."
                };
                lastError = messages[event.error] || "Voice input error: " + event.error;
                setListeningState(false);
                setStatus(lastError);
            };

            recognition.onend = function () {
                isListening = false;
                stopping = false;
                if (stopTimer) {
                    window.clearTimeout(stopTimer);
                    stopTimer = null;
                }
                setListeningState(false);
                button.disabled = false;
                const transcript = commitTranscript();
                if (transcript) {
                    setStatus("Captured. Press Enter to ask: " + transcript);
                } else if (lastError) {
                    setStatus(lastError);
                } else {
                    setStatus("No speech was recognized. Check microphone access and try again.");
                }
            };

            button.onclick = function () {
                if (isListening) {
                    isListening = false;
                    stopping = true;
                    setListeningState(false);
                    button.disabled = true;
                    const transcript = commitTranscript();
                    setStatus(transcript ? "Stopped. Captured: " + transcript : "Stopping microphone...");
                    stopTimer = window.setTimeout(function () {
                        if (!stopping) return;
                        let abortError = "";
                        try {
                            recognition.abort();
                        } catch (error) {
                            abortError = error.message;
                        }
                        stopping = false;
                        button.disabled = false;
                        setStatus(abortError
                            ? "Could not stop microphone: " + abortError
                            : transcript
                                ? "Captured. Press Enter to ask: " + transcript
                                : "Stopped, but no speech was recognized. Check microphone access and try again.");
                    }, 2000);
                    try {
                        recognition.stop();
                    } catch (error) {
                        window.clearTimeout(stopTimer);
                        stopTimer = null;
                        stopping = false;
                        button.disabled = false;
                        setStatus("Could not stop microphone: " + error.message);
                    }
                    return;
                }

                try {
                    recognition.start();
                } catch (error) {
                    setListeningState(false);
                    setStatus(error.name === "InvalidStateError"
                        ? "Speech recognition is still closing. Wait a moment, then try again."
                        : "Could not start microphone: " + error.message);
                }
            };
        }
        </script>
        """,
        height=48,
    )


def submit_question():
    question = (st.session_state.get("question_entry") or "").strip()
    if not question:
        return

    if not st.session_state.document_processed:
        st.warning("Please upload and process a PDF before asking questions.")
        return

    handle_question(question)
    st.session_state.question_entry = ""


def answer_from_chunks(question, search_index, pdf_data=None):
    q_lower = question.lower()

    # Metadata questions - generic patterns
    count_pattern = re.compile(
        r"\b(how\s+many\s+pages|number\s+of\s+pages|page\s+count|total\s+pages)\b",
        re.IGNORECASE
    )

    name_pattern = re.compile(
        r"\b(?:file|document|pdf)\s+name\b|"
        r"\bname\s+of\s+(?:the\s+)?(?:file|document|pdf)\b",
        re.IGNORECASE
    )

    if pdf_data:
        page_number = extract_page_number(q_lower)

        if page_number is not None:
            all_pages = []

            for pdf in pdf_data:
                for index, page_text in enumerate(
                    pdf.get("page_texts", []), start=1
                ):
                    all_pages.append((
                        pdf.get("name", "PDF"),
                        index,
                        page_text
                    ))

            if 1 <= page_number <= len(all_pages):
                document_name, _, page_text = all_pages[page_number - 1]

                if page_text:
                    if re.search(
                        r"\b(summary|summarize|describe|explain|about)\b",
                        q_lower
                    ):
                        summary = summarize_text(
                            page_text,
                            max_sentences=4
                        )

                        return build_systematic_response(
                            f"Here is the summary of page {page_number}.",
                            "I looked at the requested page and picked the most important lines in simple form.",
                            split_into_points(summary, max_points=4),
                            f"{document_name}, page {page_number}",
                            92,
                        )

                    return build_systematic_response(
                        f"Here is the content found on page {page_number}.",
                        "I pulled the readable text from the page you asked for.",
                        split_into_points(page_text[:700], max_points=4),
                        f"{document_name}, page {page_number}",
                        95,
                    )

                return (
                    f"I found page {page_number}, but I could not "
                    "extract readable text from it."
                )

        if count_pattern.search(q_lower):
            total_pages = sum(
                pdf.get("page_count", 0)
                for pdf in pdf_data
            )

            return build_systematic_response(
                f"The document has {total_pages} page(s).",
                "This is the total number of pages found in the uploaded PDF file(s).",
                confidence=98,
            )

        if name_pattern.search(q_lower):
            names = [
                pdf.get("name", "Unknown")
                for pdf in pdf_data
            ]

            if len(names) == 1:
                return build_systematic_response(
                    f"The document name is {names[0]}.",
                    "This is the file name of the uploaded PDF.",
                    confidence=99,
                )

            return build_systematic_response(
                f"The uploaded documents are: {', '.join(names)}.",
                "These are the file names currently available in the app.",
                confidence=99,
            )

        section_list = None
        if not is_short_fact_question(question):
            section_list = find_relevant_section_list(question, pdf_data)

        if section_list:
            points, document_name, page_number = section_list
            return build_systematic_response(
                "Here are the relevant points from the document.",
                points=points,
                source=f"{document_name}, page {page_number}",
            )

        if is_summary_request(q_lower):
            combined_pdf_text = "\n".join(
                "\n".join(pdf.get("page_texts", []))
                for pdf in pdf_data
            )

            summary = summarize_text(
                combined_pdf_text,
                max_sentences=5
            )
            is_resume = any(
                re.search(
                    r"\b(?:resume|cv)\b",
                    pdf.get("name", "").replace("_", " "),
                    re.IGNORECASE,
                )
                for pdf in pdf_data
            )
            candidate_name = (
                extract_candidate_name(pdf_data) if is_resume else None
            )
            if candidate_name:
                summary = f"- This resume belongs to {candidate_name}.\n{summary}"
            if is_resume:
                profile_line = next(
                    (
                        clean_text(line)
                        for pdf in pdf_data
                        for page_text in pdf.get("page_texts", [])
                        for line in (page_text or "").splitlines()
                        if len(clean_text(line)) > 40
                        and re.search(
                            r"\b(undergraduate|graduate|student|engineer|"
                            r"professional|developer)\b",
                            line,
                            re.IGNORECASE,
                        )
                    ),
                    None,
                )
                if profile_line:
                    summary = f"- {profile_line}\n{summary}"

            return build_systematic_response(
                "Here is the document summary.",
                "I read the main text from the PDF and converted it into simple points.",
                split_into_points(summary, max_points=5),
                source=", ".join(
                    pdf.get("name", "PDF") for pdf in pdf_data
                ),
                confidence=88,
            )

        if re.search(
            r"\b(?:whose|whoose)\s+(?:resume|cv|document)\b|"
            r"\bwho\s+is\s+this\b|"
            r"\bname\s+of\s+(?:the\s+)?(?:person|candidate)\b|"
            r"\bwho\s+does\s+this\s+resume\s+belong\s+to\b",
            q_lower,
        ):
            candidate_name = extract_candidate_name(pdf_data)

            if candidate_name:
                return build_systematic_response(
                    f"This resume appears to belong to {candidate_name}.",
                    "I found this name in the top part of the document, where resumes usually mention the candidate name.",
                    source=", ".join(
                        pdf.get("name", "PDF") for pdf in pdf_data
                    ),
                    confidence=84,
                )

            return build_systematic_response(
                "I could not identify the resume owner's name in the extracted text or file name.",
                source=", ".join(
                    pdf.get("name", "PDF") for pdf in pdf_data
                ),
                confidence=10,
            )

        if re.search(
            r"\b(?:list|show|name|what|which|give)\b.*\bprojects?\b",
            q_lower,
        ):
            project_entries = find_resume_project_entries(pdf_data)
            if project_entries:
                sources = sorted({
                    f"{document_name}, page {page_number}"
                    for _, document_name, page_number in project_entries
                })
                return build_systematic_response(
                    "Here are the projects listed in the document.",
                    points=[entry for entry, _, _ in project_entries],
                    source="; ".join(sources),
                )

        if re.search(r"\b(college|university|institute)\b", q_lower):
            college_detail = extract_education_detail(
                pdf_data,
                ["college", "university", "institute"]
            )

            if college_detail:
                return build_systematic_response(
                    "I found the college information in the document.",
                    "This line looks related to the education section.",
                    [college_detail],
                    confidence=82,
                )

        if (
            is_short_fact_question(question)
            or re.search(
                r"\b(?:tell|describe)\s+(?:me\s+)?about\b",
                q_lower,
            )
        ):
            fact_answer, fact_source = find_focused_fact_answer(
                question,
                pdf_data,
            )
            if fact_answer:
                return build_systematic_response(
                    fact_answer,
                    source=fact_source,
                    confidence=80,
                )

        if re.search(r"\bschool\b", q_lower):
            school_detail = extract_education_detail(
                pdf_data,
                ["school", "higher secondary", "secondary"]
            )

            if school_detail:
                return build_systematic_response(
                    "I found the school information in the document.",
                    "This line looks related to the school or secondary education section.",
                    [school_detail],
                    confidence=82,
                )

    # Get relevant chunks for any question
    matches = retrieve_chunks(
        question,
        search_index,
        limit=6
    )

    if not matches:
        return build_systematic_response(
            "I could not find a clear answer in the extracted text.",
            "This usually means the PDF does not contain the needed information, or the text could not be read properly from the file.",
            confidence=10,
        )

    comparison_terms = extract_comparison_terms(question)

    if comparison_terms:
        first_term, second_term = comparison_terms

        first_sentence = find_best_sentence_for_term(
            first_term,
            matches
        )

        second_sentence = find_best_sentence_for_term(
            second_term,
            matches
        )

        if first_sentence and second_sentence:
            comparison_points = [
                f"{first_term.title()}: {first_sentence[1]}",
                f"{second_term.title()}: {second_sentence[1]}",
            ]

            supporting = [
                first_sentence[2],
                second_sentence[2]
            ]

            return build_systematic_response(
                f"Here is the difference between {first_term} and {second_term}.",
                "I found separate supporting lines for both topics from the chapter instead of guessing the comparison.",
                comparison_points,
                format_sources(supporting),
                None,
            )

    selected, supporting_matches = select_best_sentences(
        question,
        matches,
        max_sentences=5
    )

    if not selected:
        combined = clean_text(
            " ".join(match["text"] for match in matches)
        )

        selected = split_into_points(
            combined[:700],
            max_points=4
        )

        supporting_matches = matches[:2]

    question_terms = expand_query_terms(question)

    support_overlap = len(
        question_terms & set(content_words(" ".join(selected)))
    )

    if support_overlap == 0:
        return build_systematic_response(
            "I could not find a reliable answer for that question in the uploaded PDF.",
            "I found some related text, but it does not directly support a correct answer. Please try asking with chapter keywords, topic names, or a page number.",
            source=format_sources(matches),
            confidence=18,
        )

    concise_answer = selected[0]

    explanation = (
        "I answered this using the most relevant lines from the chapter "
        "and avoided guessing beyond what the PDF actually says."
    )

    if is_short_fact_question(question):
        return build_systematic_response(
            concise_answer,
            source=format_sources(supporting_matches[:1] or matches[:1]),
            confidence=75,
        )

    return build_systematic_response(
        concise_answer,
        explanation,
        selected[1:5],
        format_sources(supporting_matches or matches),
        None,
    )
def get_document_summary(raw_text):
    return summarize_text(raw_text)


# generating response from user queries and displaying them accordingly
def handle_question(question):
    conversational_reply = get_conversational_reply(question)

    if conversational_reply:
        answer = conversational_reply
    else:
        answer = answer_from_chunks(
            question,
            st.session_state.search_index,
            st.session_state.pdf_data,
        )

    st.session_state.chat_history.append(
        ("user", question)
    )

    st.session_state.chat_history.append(
        ("bot", answer)
    )


def render_chat_history():
    for role, message in st.session_state.chat_history:
        if role == "user":
            st.write(
                user_template.replace("{{MSG}}", message),
                unsafe_allow_html=True
            )
        else:
            st.write(
                bot_template.replace("{{MSG}}", message),
                unsafe_allow_html=True
            )
def main():
    load_dotenv()

    st.set_page_config(
        page_title="Chat with multiple PDFs",
        page_icon=":books:",
        layout="wide"
    )

    st.write(css, unsafe_allow_html=True)

    # Initialize session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "processed_docs" not in st.session_state:
        st.session_state.processed_docs = []

    if "document_processed" not in st.session_state:
        st.session_state.document_processed = False

    if "raw_text" not in st.session_state:
        st.session_state.raw_text = ""

    if "summary" not in st.session_state:
        st.session_state.summary = None

    if "search_index" not in st.session_state:
        st.session_state.search_index = {
            "chunks": [],
            "vectorizer": None,
            "matrix": None,
            "char_vectorizer": None,
            "char_matrix": None,
            "neighbors": {},
        }

    if "pdf_data" not in st.session_state:
        st.session_state.pdf_data = []

    st.header("Chat with multiple PDFs :books:")

    with st.container():
        st.text_input(
            "Question",
            placeholder="Ask a question about your PDFs...",
            label_visibility="collapsed",
            key="question_entry",
            on_change=submit_question,
        )
        render_voice_input()

    # Display document summary
    if st.session_state.summary:
        st.markdown(
            "<div class='summary-display'>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<h3>Document Summary</h3>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<div class='summary-content'>{st.session_state.summary}</div>",
            unsafe_allow_html=True
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    # Display chat history
    st.markdown(
        "<div class='chat-area'>",
        unsafe_allow_html=True
    )

    render_chat_history()

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )

    # Sidebar
    with st.sidebar:
        st.subheader("Your documents")

        docs = st.file_uploader(
            "Upload your PDF here and click on 'Process'",
            accept_multiple_files=True,
            type=["pdf"],
        )

        if docs:
            st.markdown(
                "<div class='selected-docs'><strong>Selected PDF files</strong>"
                + "".join([
                    "<div class='selected-doc'>"
                    f"<span class='selected-doc-name'>{html_escape(doc.name)}</span>"
                    f"<span class='selected-doc-size'>{format_file_size(doc.size)}</span>"
                    "</div>"
                    for doc in docs
                ])
                + "</div>",
                unsafe_allow_html=True,
            )

        if st.button("Process"):
            if not docs:
                st.warning(
                    "Please upload at least one PDF before processing."
                )

            else:
                with st.spinner("Processing your document..."):
                    try:
                        raw_text, pdf_data = get_pdf_text(docs)

                        if not raw_text:
                            if any(
                                document.get("ocr_used")
                                for document in pdf_data
                            ):
                                st.error(
                                    "OCR ran but recovered no readable text. "
                                    "The PDF may be blank, damaged, or too low "
                                    "quality. Try the original PDF or a clearer scan."
                                )
                            else:
                                st.error(
                                    "The PDF was uploaded, but no readable text "
                                    "was found."
                                )

                        else:
                            search_index = build_search_index(pdf_data)

                            st.session_state.raw_text = raw_text
                            st.session_state.pdf_data = pdf_data
                            st.session_state.search_index = search_index

                            st.session_state.processed_docs = [
                                doc.name for doc in docs
                            ]

                            st.session_state.document_processed = True
                            st.session_state.summary = None
                            st.session_state.chat_history = []

                    except Exception as exc:
                        st.error(
                            f"Could not process the PDF: {exc}"
                        )

        # Show processed document details
        if st.session_state.document_processed:
            processed_names = ", ".join(
                st.session_state.processed_docs
            )

            st.markdown(
                "<div class='processed-box'>Document processed successfully.<br><span>"
                + html_escape(processed_names)
                + "</span></div>",
                unsafe_allow_html=True,
            )

            if any(
                document.get("ocr_used")
                for document in st.session_state.pdf_data
            ):
                st.caption(
                    "OCR was used for scanned pages. Please verify extracted "
                    "text because OCR can make recognition errors."
                )

            if st.button("Summarize Document"):
                with st.spinner("Creating summary..."):
                    st.session_state.summary = get_document_summary(
                        st.session_state.raw_text
                    )


if __name__ == "__main__":
    main()