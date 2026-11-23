import argparse
import csv
import html
import re
from collections import Counter
from pathlib import Path

import app


def normalize_answer(text):
    text = str(text or "")
    main_answer = re.search(
        r"<div class=['\"]answer-section answer-main['\"]>.*?"
        r"<div class=['\"]answer-text['\"]>(.*?)</div>",
        text,
        flags=re.DOTALL,
    )
    if main_answer:
        text = main_answer.group(1)

    plain_text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.findall(r"\w+", plain_text.lower())


def exact_match(prediction, reference):
    return normalize_answer(prediction) == normalize_answer(reference)


def token_f1(prediction, reference):
    predicted_tokens = normalize_answer(prediction)
    reference_tokens = normalize_answer(reference)

    if not predicted_tokens or not reference_tokens:
        return 0.0

    overlap = sum(
        (Counter(predicted_tokens) & Counter(reference_tokens)).values()
    )
    if not overlap:
        return 0.0

    precision = overlap / len(predicted_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def load_dataset(dataset_path):
    with open(dataset_path, newline="", encoding="utf-8-sig") as dataset_file:
        reader = csv.DictReader(dataset_file)
        columns = {
            (column or "").strip().lower(): column
            for column in (reader.fieldnames or [])
        }

        if "question" not in columns or "ground_truth" not in columns:
            raise ValueError(
                "The CSV must have 'question' and 'ground_truth' columns."
            )

        examples = []
        for row_number, row in enumerate(reader, start=2):
            question = (row.get(columns["question"]) or "").strip()
            reference = (row.get(columns["ground_truth"]) or "").strip()

            if not question and not reference:
                continue
            if not question or not reference:
                raise ValueError(
                    f"CSV row {row_number} needs both a question and a "
                    "ground_truth answer."
                )

            examples.append({
                "question": question,
                "ground_truth": reference,
            })

    if not examples:
        raise ValueError(
            "The CSV contains no labeled examples. Add question/ground_truth "
            "pairs before calculating evaluation metrics."
        )

    return examples


def evaluate(pdf_path, dataset_path):
    examples = load_dataset(dataset_path)

    with open(pdf_path, "rb") as pdf_file:
        raw_text, pdf_data = app.get_pdf_text([pdf_file])

    if not raw_text:
        if any(document.get("ocr_used") for document in pdf_data):
            raise ValueError(
                "OCR ran but recovered no readable text. The PDF may be blank, "
                "damaged, or too low quality."
            )
        raise ValueError("No readable text was extracted from the PDF.")

    search_index = app.build_search_index(pdf_data)
    results = []

    for example in examples:
        prediction = app.answer_from_chunks(
            example["question"],
            search_index,
            pdf_data,
        )
        results.append({
            "question": example["question"],
            "ground_truth": example["ground_truth"],
            "prediction": prediction,
            "exact_match": exact_match(
                prediction,
                example["ground_truth"],
            ),
            "token_f1": token_f1(
                prediction,
                example["ground_truth"],
            ),
        })

    exact_match_rate = (
        sum(result["exact_match"] for result in results) / len(results)
    )
    mean_token_f1 = (
        sum(result["token_f1"] for result in results) / len(results)
    )
    ocr_used = any(document.get("ocr_used") for document in pdf_data)

    return results, exact_match_rate, mean_token_f1, ocr_used


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the PDF question-answering app against labeled examples."
    )
    parser.add_argument("--pdf", required=True, help="PDF to evaluate against")
    parser.add_argument(
        "--dataset",
        required=True,
        help="CSV with question and ground_truth columns",
    )
    parser.add_argument(
        "--output",
        help="Optional path for per-question evaluation results CSV",
    )
    args = parser.parse_args()

    try:
        results, exact_match_rate, mean_token_f1, ocr_used = evaluate(
            args.pdf,
            args.dataset,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Questions evaluated: {len(results)}")
    print(f"Exact match: {exact_match_rate:.1%}")
    print(f"Mean token F1: {mean_token_f1:.1%}")
    print(f"OCR used: {'yes' if ocr_used else 'no'}")
    print(
        "These are automatic text-overlap metrics, not a human-verified "
        "accuracy guarantee."
    )

    if args.output:
        output_path = Path(args.output)
        with output_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as results_file:
            writer = csv.DictWriter(
                results_file,
                fieldnames=[
                    "question",
                    "ground_truth",
                    "prediction",
                    "exact_match",
                    "token_f1",
                ],
            )
            writer.writeheader()
            for result in results:
                output_row = dict(result)
                output_row["token_f1"] = f"{result['token_f1']:.4f}"
                writer.writerow(output_row)


if __name__ == "__main__":
    main()
