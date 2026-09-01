# importing dependencies
import re
from collections import defaultdict

from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components
from PyPDF2 import PdfReader

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
    return [token for token in tokenize(text) if token not in STOP_WORDS and len(token) > 1]


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
    text = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("\n", "<br>")


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


def build_systematic_response(main_answer, explanation=None, points=None, source=None, confidence=None):
    sections = [
        "<div class='answer-format'>"
        "<div class='answer-section answer-main'>"
        "<div class='answer-label'>Direct Answer</div>"
        f"<div class='answer-text'>{html_escape(main_answer)}</div>"
        "</div>"
    ]

    if explanation:
        sections.append(
            "<div class='answer-section'>"
            "<div class='answer-label'>Simple Explanation</div>"
            f"<div class='answer-text'>{html_escape(explanation)}</div>"
            "</div>"
        )

    if confidence is not None:
        sections.append(
            "<div class='answer-section answer-metric'>"
            "<div class='answer-label'>Confidence</div>"
            f"<div class='answer-badge'>{html_escape(str(confidence) + '%')}</div>"
            "</div>"
        )

    if points:
        bullet_items = "".join(f"<li>{html_escape(point)}</li>" for point in points if clean_text(point))
        if bullet_items:
            sections.append(
                "<div class='answer-section'>"
                "<div class='answer-label'>Key Points</div>"
                f"<ul class='answer-list'>{bullet_items}</ul>"
                "</div>"
            )

    if source:
        sections.append(
            "<div class='answer-section answer-source'>"
            "<div class='answer-label'>Source</div>"
            f"<div class='answer-text'>{html_escape(source)}</div>"
            "</div>"
        )

    sections.append("</div>")
    return "".join(sections)


def split_into_sentences(text):
    return [clean_text(sentence) for sentence in re.split(r"(?<=[.!?])\s+", clean_text(text)) if clean_text(sentence)]


def split_into_paragraphs(text):
    raw_paragraphs = re.split(r"\n\s*\n", text or "")
    paragraphs = [clean_text(paragraph) for paragraph in raw_paragraphs if clean_text(paragraph)]
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
    if re.search(r"(all rights reserved|copyright|www\.|http|@\w+|isbn|published by)", lowered):
        return True
    return False


def remove_headers_and_footers(page_texts):
    if not page_texts:
        return []

    normalized_pages = []
    for page_text in page_texts:
        raw_lines = [clean_text(line) for line in (page_text or "").splitlines()]
        normalized_pages.append([line for line in raw_lines if line])

    repeated_candidates = defaultdict(set)
    for page_index, lines in enumerate(normalized_pages):
        edge_lines = lines[:3] + lines[-3:]
        for line in edge_lines:
            normalized_line = re.sub(r"\d+", "<num>", line.lower())
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
            normalized_line = re.sub(r"\d+", "<num>", line.lower())
            is_edge_line = idx < 3 or idx >= max(len(lines) - 3, 0)
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
        pdf_reader = PdfReader(pdf)
        raw_pages = []
        for page in pdf_reader.pages:
            page_text = page.extract_text() or ""
            raw_pages.append(page_text)

        cleaned_page_texts = remove_headers_and_footers(raw_pages)
        raw_pdf_text = "\n".join(raw_pages)
        cleaned_pdf_text = "\n".join(cleaned_page_texts)
        pdf_text = clean_text(cleaned_pdf_text)
        text += pdf_text + "\n"
        pdf_data.append({
            "name": pdf.name,
            "page_texts": [clean_text(page_text) for page_text in cleaned_page_texts],
            "raw_text": raw_pdf_text,
            "text": pdf_text,
            "page_count": len(pdf_reader.pages),
            "has_text": bool(pdf_text),
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

            overlap_text = chunk_text[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = [clean_text(overlap_text), paragraph] if overlap_text else [paragraph]
            current = [item for item in current if item]
            current_length = len(" ".join(current))
        else:
            current.append(paragraph)
            current_length += len(paragraph) + 1

    if current:
        chunks.append(" ".join(current).strip())

    return [clean_text(chunk) for chunk in chunks if clean_text(chunk)]


def build_search_index(pdf_data):
    chunks = []
    for pdf in pdf_data:
        page_texts = pdf.get("page_texts", [])
        if page_texts:
            for page_number, page_text in enumerate(page_texts, start=1):
                for chunk_position, chunk in enumerate(get_chunks(page_text), start=1):
                    chunks.append({
                        "document": pdf.get("name", "PDF"),
                        "page": page_number,
                        "text": chunk,
                        "chunk_position": chunk_position,
                        "content_words": set(content_words(chunk)),
                        "score": 0.0,
                    })
        else:
            for chunk_position, chunk in enumerate(get_chunks(pdf.get("text", "")), start=1):
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
        grouped_chunks[(chunk["document"], chunk["page"])].append((index, chunk))

    for group_items in grouped_chunks.values():
        indexes = [index for index, _ in sorted(group_items, key=lambda item: item[1]["chunk_position"])]
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
        matrix = vectorizer.fit_transform([chunk["text"] for chunk in chunks])
        char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        char_matrix = char_vectorizer.fit_transform([chunk["text"] for chunk in chunks])
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
    chunks = search_index.get("chunks", [])
    if not chunks:
        return []

    query_terms = expand_query_terms(question)
    vectorizer = search_index.get("vectorizer")
    matrix = search_index.get("matrix")
    char_vectorizer = search_index.get("char_vectorizer")
    char_matrix = search_index.get("char_matrix")
    neighbors = search_index.get("neighbors", {})
    ranked_indexes = []
    ranked_score_map = {}

    if vectorizer is not None and matrix is not None and cosine_similarity:
        query_vector = vectorizer.transform([question])
        word_scores = cosine_similarity(query_vector, matrix).flatten()

        char_scores = None
        if char_vectorizer is not None and char_matrix is not None:
            char_query_vector = char_vectorizer.transform([question])
            char_scores = cosine_similarity(char_query_vector, char_matrix).flatten()

        scored = []
        for index, chunk in enumerate(chunks):
            keyword_overlap = len(query_terms & chunk.get("content_words", set()))
            exact_phrase_bonus = 0.15 if clean_text(question).lower() in chunk["text"].lower() else 0.0
            heading_bonus = 0.08 if any(term in chunk["text"].lower()[:180] for term in query_terms) else 0.0
            word_score = float(word_scores[index])
            char_score = float(char_scores[index]) if char_scores is not None else 0.0
            final_score = (word_score * 0.6) + (char_score * 0.15) + (keyword_overlap * 0.18) + exact_phrase_bonus + heading_bonus
            scored.append((final_score, index))
            ranked_score_map[index] = final_score

        scored.sort(reverse=True)
        ranked_indexes = [index for score, index in scored if score > 0][:limit]
    else:
        fallback_scores = []
        for index, chunk in enumerate(chunks):
            overlap = len(query_terms & set(tokenize(chunk["text"])))
            if overlap > 0:
                fallback_scores.append((overlap, index))
                ranked_score_map[index] = min(overlap / max(len(query_terms), 1), 1.0)
        fallback_scores.sort(reverse=True)
        ranked_indexes = [index for _, index in fallback_scores[:limit]]

    if not ranked_indexes:
        return []

    chosen_indexes = []
    seen_indexes = set()
    for index in ranked_indexes:
        if index not in seen_indexes:
            chosen_indexes.append(index)
            seen_indexes.add(index)
        for neighbor_index in neighbors.get(index, []):
            if len(chosen_indexes) >= limit + 2:
                break
            if neighbor_index not in seen_indexes:
                chosen_indexes.append(neighbor_index)
                seen_indexes.add(neighbor_index)

    results = []
    for index in chosen_indexes[: limit + 2]:
        chunk = dict(chunks[index])
        chunk["score"] = float(ranked_score_map.get(index, chunk.get("score", 0.0)))
        results.append(chunk)
    return results


def summarize_text(raw_text, max_sentences=6):
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(raw_text))
    sentences = [sentence for sentence in sentences if len(sentence) > 35]
    if not sentences:
        return "The uploaded PDF was processed, but it does not contain enough readable text to summarize."
    return "\n".join([f"- {sentence}" for sentence in sentences[:max_sentences]])


def extract_candidate_name(pdf_data):
    lines = []
    for pdf in pdf_data or []:
        raw_text = pdf.get("raw_text") or pdf.get("text", "")
        lines.extend(clean_text(line) for line in raw_text.splitlines())

    skip_terms = {
        "resume", "cv", "curriculum", "vitae", "email", "phone", "mobile", "address",
        "education", "experience", "skills", "project", "projects", "profile",
        "summary", "objective", "linkedin", "github",
    }

    for line in lines[:20]:
        if not line or any(term in line.lower() for term in skip_terms):
            continue
        if re.search(r"[@\d]", line):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Z][A-Za-z.'-]*", word) for word in words):
            return line
    return None


def extract_education_detail(pdf_data, keywords):
    lines = []
    for pdf in pdf_data or []:
        raw_text = pdf.get("raw_text") or pdf.get("text", "")
        lines.extend(clean_text(line) for line in raw_text.splitlines())

    for line in lines:
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in keywords):
            return line

    combined_text = " ".join((pdf.get("text", "") for pdf in pdf_data or []))
    pattern = re.compile(rf"([^.\\n]{{0,80}}(?:{'|'.join(re.escape(keyword) for keyword in keywords)})[^.\\n]{{0,120}})", re.IGNORECASE)
    match = pattern.search(combined_text)
    return clean_text(match.group(1)) if match else None


def extract_page_number(question):
    ordinal_match = re.search(r"\b(\d+)(?:st|nd|rd|th)\s+page\b", question.lower())
    if ordinal_match:
        return int(ordinal_match.group(1))

    page_match = re.search(r"\bpage\s+(\d+)\b", question.lower())
    if page_match:
        return int(page_match.group(1))

    return None


def is_summary_request(question):
    q = question.lower()
    summary_terms = re.search(r"\b(summary|summarize|overview|gist|brief)\b", q)
    document_terms = re.search(r"\b(document|pdf|chapter|file|text|content|whole)\b", q)
    broad_prompt = re.search(r"\b(what is this document about|what is this chapter about|give me a summary|summarize this)\b", q)
    return bool(broad_prompt or (summary_terms and document_terms))


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
            formatted.append(f"{document}, page {', '.join(str(page) for page in pages)}")
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
    return max(float(match.get("score", 0.0)) for match in matches)


def get_conversational_reply(question):
    q = clean_text(question).lower()
    if not q:
        return None

    if re.fullmatch(r"(hi|hello|hey|hii|hiii|hola|good morning|good afternoon|good evening)", q):
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

    if re.fullmatch(r"(thank you|thanks|thankyou|thx|thanks a lot|thank you so much)", q):
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

    if re.fullmatch(r"(bye|goodbye|see you|ok bye|bye bye)", q):
        return build_systematic_response(
            "Goodbye and take care.",
            "Come back anytime if you want help with another PDF or another question.",
            confidence=99,
        )

    if re.fullmatch(r"(how are you|how are you doing|how r u)", q):
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
    if not sentence_words:
        return 0

    overlap = len(question_terms & sentence_words)
    phrase_bonus = 2 if clean_text(question_text).lower() in sentence.lower() else 0
    starts_like_definition = 1 if re.search(r"\b(is|refers to|means|defined as)\b", sentence.lower()) else 0
    length_bonus = min(len(sentence) / 180, 1.0)
    return (overlap * 3) + phrase_bonus + starts_like_definition + length_bonus


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
            score = (overlap * 3) + min(len(sentence) / 200, 1.0)
            if best is None or score > best[0]:
                best = (score, sentence, match)
    return best


def select_best_sentences(question, matches, max_sentences=5):
    question_terms = expand_query_terms(question)
    candidates = []

    for match in matches:
        sentences = split_into_sentences(match["text"])
        for sentence in sentences:
            score = sentence_score(sentence, question_terms, question)
            if score > 0:
                candidates.append((score, sentence, match))

    candidates.sort(key=lambda item: item[0], reverse=True)

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
        <div style="margin: 0.35rem 0 0.85rem 0;">
            <button id="voice-btn" style="background:#17466f;color:white;border:none;border-radius:8px;padding:0.65rem 1rem;font-weight:700;cursor:pointer;">
                Start Voice Input
            </button>
            <div id="voice-status" style="margin-top:0.45rem;color:#65758a;font-size:0.92rem;">
                Speak your question in Chrome or Edge, then press Enter in the text box.
            </div>
        </div>
        <script>
        const button = document.getElementById("voice-btn");
        const status = document.getElementById("voice-status");
        const SpeechRecognition = window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            button.disabled = true;
            button.style.opacity = "0.6";
            status.textContent = "Voice input is not supported in this browser. Please use Chrome or Edge.";
        } else {
            const recognition = new SpeechRecognition();
            recognition.lang = "en-US";
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            recognition.onstart = function () {
                status.textContent = "Listening... speak now.";
                button.textContent = "Listening...";
            };

            recognition.onresult = function (event) {
                const transcript = event.results[0][0].transcript || "";
                const parentDoc = window.parent.document;
                const input = parentDoc.querySelector('input[aria-label="Ask question from your document:"]')
                    || parentDoc.querySelector('input[type="text"]');

                if (input) {
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, "value").set;
                    nativeSetter.call(input, transcript);
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    input.focus();
                    status.textContent = "Voice captured: " + transcript + " Press Enter to ask.";
                } else {
                    status.textContent = "Voice captured, but the text box was not found.";
                }
            };

            recognition.onerror = function (event) {
                status.textContent = "Voice input error: " + event.error;
                button.textContent = "Start Voice Input";
            };

            recognition.onend = function () {
                button.textContent = "Start Voice Input";
            };

            button.onclick = function () {
                recognition.start();
            };
        }
        </script>
        """,
        height=110,
    )


def answer_from_chunks(question, search_index, pdf_data=None):
    q_lower = question.lower()
    
    # Metadata questions - generic patterns
    count_pattern = re.compile(r"\b(how\s+many\s+pages|number\s+of\s+pages|page\s+count|total\s+pages)\b", re.IGNORECASE)
    name_pattern = re.compile(r"\b(name\s+of|file\s+name|document\s+name|called|what\s+is\s+.*name|title)\b", re.IGNORECASE)
    if pdf_data:
        page_number = extract_page_number(q_lower)
        if page_number is not None:
            all_pages = []
            for pdf in pdf_data:
                for index, page_text in enumerate(pdf.get("page_texts", []), start=1):
                    all_pages.append((pdf.get("name", "PDF"), index, page_text))

            if 1 <= page_number <= len(all_pages):
                document_name, _, page_text = all_pages[page_number - 1]
                if page_text:
                    if re.search(r"\b(summary|summarize|describe|explain|about)\b", q_lower):
                        summary = summarize_text(page_text, max_sentences=4)
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
                return f"I found page {page_number}, but I could not extract readable text from it."

        if count_pattern.search(q_lower):
            total_pages = sum(pdf.get("page_count", 0) for pdf in pdf_data)
            return build_systematic_response(
                f"The document has {total_pages} page(s).",
                "This is the total number of pages found in the uploaded PDF file(s).",
                confidence=98,
            )
        
        if name_pattern.search(q_lower):
            names = [pdf.get("name", "Unknown") for pdf in pdf_data]
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
        
        if is_summary_request(q_lower):
            combined_pdf_text = " ".join(pdf.get("text", "") for pdf in pdf_data)
            summary = summarize_text(combined_pdf_text, max_sentences=5)
            return build_systematic_response(
                "Here is the document summary.",
                "I read the main text from the PDF and converted it into simple points.",
                split_into_points(summary, max_points=5),
                confidence=88,
            )

        if re.search(r"\b(whose\s+(resume|cv|document)|who\s+is\s+this|name\s+of\s+(the\s+)?(person|candidate)|who\s+does\s+this\s+resume\s+belong\s+to)\b", q_lower):
            candidate_name = extract_candidate_name(pdf_data)
            if candidate_name:
                return build_systematic_response(
                    f"This resume appears to belong to {candidate_name}.",
                    "I found this name in the top part of the document, where resumes usually mention the candidate name.",
                    confidence=84,
                )

        if re.search(r"\b(college|university|institute)\b", q_lower):
            college_detail = extract_education_detail(pdf_data, ["college", "university", "institute"])
            if college_detail:
                return build_systematic_response(
                    "I found the college information in the document.",
                    "This line looks related to the education section.",
                    [college_detail],
                    confidence=82,
                )

        if re.search(r"\bschool\b", q_lower):
            school_detail = extract_education_detail(pdf_data, ["school", "higher secondary", "secondary"])
            if school_detail:
                return build_systematic_response(
                    "I found the school information in the document.",
                    "This line looks related to the school or secondary education section.",
                    [school_detail],
                    confidence=82,
                )
    
    # Get relevant chunks for any question
    matches = retrieve_chunks(question, search_index, limit=6)
    if not matches:
        return build_systematic_response(
            "I could not find a clear answer in the extracted text.",
            "This usually means the PDF does not contain the needed information, or the text could not be read properly from the file.",
            confidence=10,
        )

    comparison_terms = extract_comparison_terms(question)
    if comparison_terms:
        first_term, second_term = comparison_terms
        first_sentence = find_best_sentence_for_term(first_term, matches)
        second_sentence = find_best_sentence_for_term(second_term, matches)

        if first_sentence and second_sentence:
            comparison_points = [
                f"{first_term.title()}: {first_sentence[1]}",
                f"{second_term.title()}: {second_sentence[1]}",
            ]
            supporting = [first_sentence[2], second_sentence[2]]
            return build_systematic_response(
                f"Here is the difference between {first_term} and {second_term}.",
                "I found separate supporting lines for both topics from the chapter instead of guessing the comparison.",
                comparison_points,
                format_sources(supporting),
                normalize_confidence(best_match_score(supporting)),
            )

    selected, supporting_matches = select_best_sentences(question, matches, max_sentences=5)

    if not selected:
        combined = clean_text(" ".join(match["text"] for match in matches))
        selected = split_into_points(combined[:700], max_points=4)
        supporting_matches = matches[:2]

    question_terms = expand_query_terms(question)
    support_overlap = len(question_terms & set(content_words(" ".join(selected))))

    if support_overlap == 0:
        return build_systematic_response(
            "I could not find a reliable answer for that question in the uploaded PDF.",
            "I found some related text, but it does not directly support a correct answer. Please try asking with chapter keywords, topic names, or a page number.",
            source=format_sources(matches),
            confidence=18,
        )

    concise_answer = selected[0]
    explanation = "I answered this using the most relevant lines from the chapter and avoided guessing beyond what the PDF actually says."
    return build_systematic_response(
        concise_answer,
        explanation,
        selected[1:5],
        format_sources(supporting_matches or matches),
        normalize_confidence(best_match_score(supporting_matches or matches)),
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
    st.session_state.chat_history.append(("user", question))
    st.session_state.chat_history.append(("bot", answer))


def render_chat_history():
    for role, message in st.session_state.chat_history:
        if role == "user":
            st.write(user_template.replace("{{MSG}}", message), unsafe_allow_html=True)
        else:
            st.write(bot_template.replace("{{MSG}}", message), unsafe_allow_html=True)


def main():
    load_dotenv()
    st.set_page_config(page_title="Chat with multiple PDFs", page_icon=":books:")
    st.write(css, unsafe_allow_html=True)

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
        st.session_state.search_index = {"chunks": [], "vectorizer": None, "matrix": None}

    if "pdf_data" not in st.session_state:
        st.session_state.pdf_data = []

    st.header("Chat with multiple PDFs :books:")
    question = st.text_input("Ask question from your document:")
    render_voice_input()
    if question:
        if st.session_state.document_processed:
            handle_question(question)
        else:
            st.warning("Please upload and process a PDF before asking questions.")

    if st.session_state.summary:
        st.markdown("<div class='summary-display'>", unsafe_allow_html=True)
        st.markdown("<h3>Document Summary</h3>", unsafe_allow_html=True)
        st.markdown(f"<div class='summary-content'>{st.session_state.summary}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='chat-area'>", unsafe_allow_html=True)
    render_chat_history()
    st.markdown("</div>", unsafe_allow_html=True)

    with st.sidebar:
        st.subheader("Your documents")
        docs = st.file_uploader("Upload your PDF here and click on 'Process'", accept_multiple_files=True)
        if docs:
            st.markdown(
                "<div class='selected-docs'><strong>Selected PDF files</strong>"
                + "".join([f"<div class='selected-doc'>{doc.name}</div>" for doc in docs])
                + "</div>",
                unsafe_allow_html=True,
            )

        if st.button("Process"):
            if not docs:
                st.warning("Please upload at least one PDF before processing.")
            else:
                with st.spinner("Processing your document..."):
                    raw_text, pdf_data = get_pdf_text(docs)
                    if not raw_text:
                        st.error("The PDF was uploaded, but no readable text was found.")
                    else:
                        search_index = build_search_index(pdf_data)
                        st.session_state.raw_text = raw_text
                        st.session_state.pdf_data = pdf_data
                        st.session_state.search_index = search_index
                        st.session_state.processed_docs = [doc.name for doc in docs]
                        st.session_state.document_processed = True
                        st.session_state.summary = None
                        st.session_state.chat_history = []

        if st.session_state.document_processed:
            processed_names = ", ".join(st.session_state.processed_docs)
            st.markdown(
                f"<div class='processed-box'>Document processed successfully.<br><span>{processed_names}</span></div>",
                unsafe_allow_html=True,
            )

        if st.session_state.document_processed:
            if st.button("Summarize Document"):
                with st.spinner("Creating summary..."):
                    st.session_state.summary = get_document_summary(st.session_state.raw_text)


if __name__ == "__main__":
    main()