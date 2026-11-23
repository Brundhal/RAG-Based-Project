import re
import unittest

import app


class RetrievalQualityTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {
                "name": "biology_lesson.pdf",
                "page_count": 2,
                "page_texts": [
                    (
                        "Photosynthesis\n"
                        "Photosynthesis is the process by which green plants "
                        "use light to combine water and carbon dioxide to "
                        "produce carbohydrates.\n"
                        "Chlorophyll absorbs light energy for this process."
                    ),
                    (
                        "Significance of photosynthesis\n"
                        "1. Photosynthesis converts light energy into "
                        "chemical energy.\n"
                        "2. It releases oxygen into the atmosphere."
                    ),
                ],
                "text": (
                    "Photosynthesis is the process by which green plants use "
                    "light to combine water and carbon dioxide to produce "
                    "carbohydrates. Chlorophyll absorbs light energy for this "
                    "process. Photosynthesis converts light energy into "
                    "chemical energy. It releases oxygen into the atmosphere."
                ),
                "raw_text": "",
                "has_text": True,
            }
        ]
        self.search_index = app.build_search_index(self.documents)

    def make_resume_document(self):
        page_texts = [
            (
                "Brundha L\n"
                "Artificial Intelligence and Machine Learning undergraduate "
                "at University Visvesvaraya College of Engineering (UVCE) "
                "with interests in Artificial Intelligence, Machine "
                "Learning and Full Stack Development.\n"
                "Familiar with Python, Java, SQL, HTML, CSS, and JavaScript.\n"
                "AI/ML: Machine Learning, Deep Learning, Generative AI, "
                "LLMs, LangChain, RAG\n"
                "Improved information accessibility through intelligent search.\n"
                "Projects\n"
                "Passionate about building practical projects and "
                "continuously learning emerging technologies.\n"
                "AI Resume Analyzer \u2022 Developed a web application to "
                "analyze resumes and extract technical skills."
            ),
            (
                "College Clubs Website \u2022 Designed webpages for college clubs "
                "and student activities.\n"
                "Travel Guide Website \u2022 Developed a responsive travel "
                "information website using HTML, CSS and JavaScript.\n"
                "Improved accessibility of club-related information."
            ),
        ]
        return [{
            "name": "Brundha L_U25UV23T006013_AIML_Resume (2).pdf",
            "page_count": len(page_texts),
            "page_texts": page_texts,
            "text": "\n".join(page_texts),
            "raw_text": "\n".join(page_texts),
        }]

    def answer_resume_question(self, question):
        documents = self.make_resume_document()
        search_index = app.build_search_index(documents)
        return app.answer_from_chunks(question, search_index, documents)

    def test_document_name_question_uses_uploaded_metadata(self):
        answer = app.answer_from_chunks(
            "What is the name of the document?",
            self.search_index,
            self.documents,
        )

        self.assertIn("biology_lesson.pdf", answer)
        self.assertNotIn("chlorophyll absorbs", answer.lower())

    def test_general_about_question_returns_summary(self):
        answer = app.answer_from_chunks(
            "What is the document about?",
            self.search_index,
            self.documents,
        )

        self.assertIn("photosynthesis", answer.lower())
        self.assertNotIn("could not find a clear answer", answer.lower())
        self.assertNotIn("direct answer", answer.lower())
        self.assertNotIn("simple explanation", answer.lower())
        self.assertNotIn("key points", answer.lower())
        self.assertNotIn("here is the document summary", answer.lower())

    def test_definition_question_skips_question_heading(self):
        answer = app.answer_from_chunks(
            "What is photosynthesis?",
            self.search_index,
            self.documents,
        )
        direct_answer = re.search(
            r"answer-text'>(.*?)</div>",
            answer,
        ).group(1)

        self.assertIn("green plants", direct_answer.lower())
        self.assertNotEqual(direct_answer.strip(), "Photosynthesis")

    def test_retrieval_returns_the_relevant_page(self):
        matches = app.retrieve_chunks(
            "How does photosynthesis release oxygen?",
            self.search_index,
        )

        self.assertTrue(matches)
        self.assertIn(2, {match["page"] for match in matches[:2]})

    def test_heading_matched_list_returns_section_points(self):
        answer = app.answer_from_chunks(
            "What is the importance of photosynthesis?",
            self.search_index,
            self.documents,
        )

        self.assertIn("light energy into chemical energy", answer.lower())
        self.assertIn("releases oxygen", answer.lower())
        self.assertIn("page 2", answer.lower())
        self.assertIn("significance", app.expand_query_terms("importance"))

    def test_answers_have_no_section_labels_but_keep_source(self):
        answer = app.build_systematic_response(
            "The process converts light energy into chemical energy.",
            explanation="This is a redundant explanation.",
            points=["Plants release oxygen during the process."],
            source="biology_lesson.pdf, page 2",
        )

        self.assertNotIn("Direct Answer", answer)
        self.assertNotIn("Simple Explanation", answer)
        self.assertNotIn("Key Points", answer)
        self.assertIn("<strong>Source:</strong>", answer)
        self.assertNotIn("redundant explanation", answer)
        self.assertIn("biology_lesson.pdf, page 2", answer)

    def test_resume_summary_mentions_candidate_profile(self):
        answer = self.answer_resume_question("What is this document about?")

        self.assertIn("undergraduate", answer.lower())
        self.assertIn("artificial intelligence", answer.lower())
        self.assertIn("Brundha", answer)

    def test_project_list_returns_project_entries(self):
        answer = self.answer_resume_question("List the projects")

        self.assertIn("AI Resume Analyzer", answer)
        self.assertIn("College Clubs Website", answer)
        self.assertIn("Travel Guide Website", answer)
        self.assertNotIn("Passionate about building practical projects", answer)

    def test_club_website_question_returns_matching_project(self):
        answer = self.answer_resume_question("tell about the club website")

        self.assertIn("College Clubs Website", answer)
        self.assertIn("Designed webpages", answer)
        self.assertNotIn("Travel Guide Website", answer)
        self.assertIn("page 2", answer.lower())

    def test_misspelled_resume_owner_question_returns_candidate(self):
        answer = self.answer_resume_question("whoose resume is this?")

        self.assertIn("Brundha L", answer)
        self.assertNotIn("AI Resume Analyzer", answer)


if __name__ == "__main__":
    unittest.main()
