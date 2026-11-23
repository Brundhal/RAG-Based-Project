import unittest
from unittest.mock import patch

import app


class RetrievalAccuracyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = [
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
                        "Photosynthesis converts light energy into chemical "
                        "energy that plants can store and use.\n"
                        "The process also releases oxygen into the atmosphere."
                    ),
                ],
                "text": (
                    "Photosynthesis is the process by which green plants use "
                    "light to combine water and carbon dioxide to produce "
                    "carbohydrates. Chlorophyll absorbs light energy for this "
                    "process. Photosynthesis converts light energy into "
                    "chemical energy that plants can store and use. The process "
                    "also releases oxygen into the atmosphere."
                ),
                "raw_text": "",
                "has_text": True,
            }
        ]
        cls.search_index = app.build_search_index(cls.documents)

    def test_document_name_comes_from_uploaded_metadata(self):
        answer = app.answer_from_chunks(
            "What is the name of the doucment?",
            self.search_index,
            self.documents,
        )

        self.assertIn("biology_lesson.pdf", answer)

    def test_broad_overview_summarizes_uploaded_content(self):
        answer = app.answer_from_chunks(
            "What is the doucment about?",
            self.search_index,
            self.documents,
        )

        self.assertIn("photosynthesis", answer.lower())
        self.assertIn("biology_lesson.pdf", answer)

    def test_pronoun_overview_summarizes_multiple_resume_topics(self):
        resume = [{
            "name": "sample_resume.pdf",
            "page_count": 2,
            "page_texts": [
                "\n".join([
                    "Computer science graduate with experience building data applications and collaborating on software teams.",
                    "Earned a Bachelor of Science in Computer Science with coursework in databases and machine learning.",
                    "Technical skills include Python, Java, SQL, web development, and data analysis.",
                ]),
                "\n".join([
                    "Worked as a software intern developing internal tools and automating recurring reports.",
                    "Academic Projects",
                    "Worked with a team to develop a website displaying information about various college clubs.",
                ]),
            ],
            "text": "",
            "raw_text": "",
        }]
        resume_index = app.build_search_index(resume)
        answer = app.answer_from_chunks(
            "What is it about?",
            resume_index,
            resume,
        )
        answer_text = answer.lower()

        self.assertIn("computer science", answer_text)
        self.assertIn("technical skills", answer_text)
        self.assertIn("software intern", answer_text)
        self.assertIn("college clubs", answer_text)

    def test_semantic_and_lexical_retrieval_rank_supporting_page(self):
        matches = app.retrieve_chunks(
            "How does photosynthesis release oxygen?",
            self.search_index,
        )

        self.assertTrue(matches)
        self.assertIn(2, {match["page"] for match in matches[:2]})

    def test_relevant_passage_is_returned_without_an_api_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            answer = app.answer_from_chunks(
                "How does photosynthesis release oxygen?",
                self.search_index,
                self.documents,
            )

        self.assertIn("releases oxygen", answer.lower())
        self.assertIn("page 2", answer.lower())

    def test_misspelled_general_name_request_still_uses_metadata(self):
        self.assertTrue(
            app.is_document_name_request("Wha t is the name of the doucment?")
        )
        self.assertTrue(app.is_summary_request("What is the doucment about?"))


if __name__ == "__main__":
    unittest.main()
