# PDF Intelligence System Using Retrieval-Augmented Generation (RAG)

## 1. Project Overview

The PDF Intelligence System is an AI-based application that allows users to upload PDF documents and ask questions using natural language.

The system retrieves relevant information from uploaded documents and generates answers based on the available content. It uses Streamlit for the user interface, FAISS for vector search, Sentence Transformers for embeddings, and a locally running Qwen model through Ollama.

## 2. Technologies Used

- Python
- Streamlit
- FAISS
- Sentence Transformers
- all-MiniLM-L6-v2 Embedding Model
- Qwen2.5:1.5b LLM
- Ollama
- TF-IDF
- PyPDF2
- Tesseract OCR (optional)

## 3. Main Features

1. Upload and process PDF documents.
2. Ask questions about uploaded PDFs using natural language.
3. Retrieve relevant information using semantic and lexical search.
4. Generate answers using a locally running language model.
5. Display source document and page information.
6. Support scanned PDFs through optional OCR.
7. Evaluate answer quality using a prepared question-and-answer dataset.

## 4. How the System Works

1. The user uploads one or more PDF documents.
2. Text is extracted from the uploaded PDFs.
3. Optional OCR is used for scanned PDFs.
4. The extracted text is divided into smaller chunks.
5. Sentence Transformers converts text into numerical embeddings.
6. FAISS supports semantic similarity search, while lexical retrieval helps identify relevant text.
7. Relevant information is passed to the Qwen language model through Ollama.
8. The system generates an answer using the retrieved document information and provides source references.

## 5. Installation and Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/Brundhal/RAG-Based-Project.git
cd RAG-Based-Project
```

### Step 2: Create a Python Environment

Use Python 3.11.

```bash
python -m venv venv
```

Activate the environment on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Install and Configure Ollama

Install Ollama on your computer.

Download the required model:

```bash
ollama pull qwen2.5:1.5b
```

Make sure Ollama is running before asking questions in the application.

### Step 5: Optional OCR Setup

Install the optional Python packages:

```bash
pip install -r requirements-ocr.txt
```

For scanned PDF support, install Tesseract OCR separately and ensure that `tesseract.exe` is available through PATH.

### Step 6: Run the Application

```bash
streamlit run app.py
```

Open the following address in your browser:

```text
http://localhost:8501
```

## 6. Answer Evaluation

The project includes an evaluation script to compare generated answers with manually prepared reference answers.

The evaluation dataset should contain:

- question
- ground_truth

Example:

```csv
question,ground_truth
"What does OCR mean?","Optical character recognition"
```

Run the evaluation script:

```bash
python evaluate_accuracy.py --pdf "path/to/document.pdf" --dataset "path/to/evaluation_dataset.csv" --output evaluation_results.csv
```

The evaluation metrics help assess answer quality on the selected dataset. They do not guarantee accuracy for every PDF or question.

## 7. Important Notes

- The embedding model may download automatically the first time it is used.
- Ollama and the Qwen model must be installed separately.
- OCR is optional and requires a separate Tesseract installation.
- Answers depend on the quality of the uploaded PDFs and the retrieved information.
- Always verify important answers against the original document.

## 8. Future Enhancements

- Improve retrieval accuracy.
- Add voice-based question input and answer output.
- Support more document formats.
- Improve handling of large PDF files.
- Enhance answer evaluation and source verification.

## 9. License

This project is distributed under the license included in the repository.