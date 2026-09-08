from google import genai
from app.core.config import settings
from app.services.validator_service import validate_document
from app.services.document_analyser import parse_gemini_response

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_questions(file_bytes: bytes, filename: str, selected_cert_type: str) -> dict:
    """Generates 5 application/reasoning questions across the candidate's verified subjects."""
    val_res = validate_document(file_bytes, filename, selected_cert_type)
    extracted = val_res.get("extracted_info", {})
    candidate_name = extracted.get("candidate_name", "Candidate")
    exam_year = extracted.get("exam_year", "N/A")
    subject_list = extracted.get("subjects", [])

    prompt = f"""
Task: You are an academic assessment engine evaluating whether a candidate genuinely understands the subjects listed on their academic certificate.

Specifics:
1. Generate exactly 5 assessment questions.
2. Each question must come from a different subject in the candidate's subject list.
3. Questions must test practical understanding, reasoning, or application of knowledge.
4. Questions must be answerable within 30-45 seconds.
5. Difficulty must remain basic to intermediate.
6. Avoid simple memorization or yes/no questions.
7. Return ONLY valid JSON with no markdown.

Candidate Information:
- Candidate Name: {candidate_name}
- Exam Year: {exam_year}
- Subjects Studied: {subject_list}

JSON RESPONSE FORMAT:
{{
    "questions": [
        {{
            "id": 1,
            "subject": "",
            "question": "",
            "difficulty": "basic"
        }},
        {{
            "id": 2,
            "subject": "",
            "question": "",
            "difficulty": "basic"
        }},
        {{
            "id": 3,
            "subject": "",
            "question": "",
            "difficulty": "intermediate"
        }},
        {{
            "id": 4,
            "subject": "",
            "question": "",
            "difficulty": "basic"
        }},
        {{
            "id": 5,
            "subject": "",
            "question": "",
            "difficulty": "intermediate"
        }}
    ]
}}
"""
    try:
        gemini_response = client.models.generate_content(
            model=settings.GEMINI_EXAMINER_MODEL,
            contents=prompt,
        )
        result = parse_gemini_response(gemini_response.text)
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "questions": []}


def evaluate_answers(questions: list[dict], answers: list[str], extracted_info: dict) -> dict:
    """Strictly assesses candidate answers and calculates knowledge score (0-100)."""
    qa_pairs = []
    for i, q in enumerate(questions):
        ans = answers[i] if i < len(answers) else "No answer provided"
        qa_pairs.append({
            "subject": q.get("subject", ""),
            "question": q.get("question", ""),
            "answer": ans
        })

    prompt = f"""
Task: You are a strict academic examiner evaluating whether a candidate genuinely understands the subjects listed on their academic certificate.

Specifics:
1. Evaluate each candidate answer independently.
2. Score every answer from 0 to 10 based on correctness and reasoning.
3. Be strict and evidence-based. Vague, generic, or copied answers must score low. Blank answers = 0.
4. Return ONLY valid JSON with no markdown.

Question and Answer Pairs:
{qa_pairs}

SCORING GUIDE:
- 9-10 = Excellent understanding with accurate reasoning
- 7-8 = Good understanding with minor omissions
- 5-6 = Partial understanding with noticeable gaps
- 3-4 = Weak understanding
- 0-2 = No understanding, irrelevant, or blank

KNOWLEDGE SCORE:
Calculate: (sum of individual scores / 50) * 100

JSON RESPONSE FORMAT:
{{
    "individual_scores": [0, 0, 0, 0, 0],
    "knowledge_score": 0,
    "assessment": "",
    "feedback": ["", "", "", "", ""]
}}
"""
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_EXAMINER_MODEL,
            contents=prompt,
        )
        result = parse_gemini_response(response.text)
        result["success"] = True
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
