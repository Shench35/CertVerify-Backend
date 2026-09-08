import io
import re
import json
from pathlib import Path
from google import genai
from PIL import Image
import fitz  # PyMuPDF
from app.core.config import settings
from app.services.template_service import get_template

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def load_image_from_upload(file_bytes: bytes, filename: str) -> Image.Image:
    """Convert uploaded file (image or PDF) to a PIL Image."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        first_page = pdf_document[0]
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for forensic clarity
        pix = first_page.get_pixmap(matrix=mat)
        image_bytes = pix.tobytes("png")
        return Image.open(io.BytesIO(image_bytes))
    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return Image.open(io.BytesIO(file_bytes))
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def parse_gemini_response(response_text: str) -> dict:
    """Safely parse Gemini JSON output with self-healing fallback."""
    cleaned = re.sub(r'```json|```', '', response_text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fix_prompt = f"""
        Fix the following invalid JSON string and return ONLY valid JSON with no markdown:
        {cleaned}
        """
        fixed = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=fix_prompt,
        )
        cleaned_fixed = re.sub(r'```json|```', '', fixed.text).strip()
        return json.loads(cleaned_fixed)


def analyse_certificate(
    file_bytes: bytes,
    filename: str,
    selected_cert_type: str
) -> dict:
    """Sends certificate to Gemini with forensic standard prompt."""
    try:
        image = load_image_from_upload(file_bytes, filename)
    except Exception as e:
        return {"success": False, "error": f"Could not process file: {str(e)}"}

    template = get_template(selected_cert_type)
    subject_count_note = (
        'The last row of the results table contains "SUBJECT RECORDED" followed by a word like "EIGHT" or "NINE" — this is the subject count, NOT a grade.'
        if selected_cert_type.upper() == "WAEC"
        else "Use the certificate type's own results-table layout; do not require the WAEC SUBJECT RECORDED row."
    )

    prompt = f"""
Task: You are an expert forensic document analyst specializing in Nigerian academic certificates with 20 years of experience verifying WAEC and NECO certificates.

Specifics:
1. Determine whether the uploaded document is actually a {selected_cert_type} certificate.
2. If the document is not a {selected_cert_type} certificate, identify what it most likely is.
3. If it matches the expected certificate type, validate it against the provided authenticity standards.
4. Return ONLY valid JSON with no markdown, explanations, or extra text.

REFERENCE STANDARDS:
- Issuing body: {template['issuing_body']}
- Required text markers: {template['required_text_markers']}
- Required fields: {template['required_fields']}
- Valid grade format: {template['grade_format']}
- Valid year range: {template['valid_year_range']}
- QR code expected: {template['has_qr_code']}
- Candidate photo expected: {template['has_candidate_photo']}
- Colour scheme: {template['colour_scheme']}
- Layout pattern: {template['layout']}
- {subject_count_note}

SCORING GUIDELINES:
- 90-100: Strongly authentic with minimal inconsistencies
- 70-89: Mostly valid with minor concerns
- 40-69: Suspicious inconsistencies detected
- 0-39: High risk or likely fraudulent

JSON RESPONSE FORMAT:
{{
    "is_correct_type": true,
    "detected_type": "",
    "type_mismatch_message": null,
    "authenticity_score": 0,
    "verdict": "",
    "extracted_info": {{
        "candidate_name": "",
        "registration_number": "",
        "exam_year": "",
        "school_name": "",
        "date_of_birth": "",
        "gender": "",
        "subjects": [
            {{
                "subject": "",
                "grade": "",
                "remark": ""
            }}
        ],
        "subject_count": 0,
        "certificate_number": ""
    }},
    "field_checks": {{
        "candidate_photo_present": false,
        "qr_code_present": false,
        "seal_present": false,
        "all_required_text_present": false,
        "fonts_consistent": false,
        "grades_valid_format": false,
        "signatures_present": false
    }},
    "flagged_issues": [],
    "tampering_signs": [],
    "confidence_note": ""
}}
"""
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[prompt, image],
        )
        result = parse_gemini_response(response.text)
    except Exception as e:
        return {"success": False, "error": f"AI analysis error: {str(e)}"}

    if not result.get("is_correct_type", True):
        return {
            "success": True,
            "type_mismatch": True,
            "message": result.get(
                "type_mismatch_message",
                f"Document does not appear to be a {selected_cert_type} certificate. It looks like: {result.get('detected_type', 'unknown document')}"
            ),
            "detected_type": result.get("detected_type", "unknown")
        }

    return {
        "success": True,
        "type_mismatch": False,
        "cert_type": selected_cert_type,
        "authenticity_score": result.get("authenticity_score", 0),
        "verdict": result.get("verdict", "HIGH_RISK"),
        "extracted_info": result.get("extracted_info", {}),
        "field_checks": result.get("field_checks", {}),
        "flagged_issues": result.get("flagged_issues", []),
        "tampering_signs": result.get("tampering_signs", []),
        "confidence_note": result.get("confidence_note", ""),
        "raw_gemini_result": result
    }
