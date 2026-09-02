import re
from app.services.document_analyser import analyse_certificate
from app.services.template_service import (
    get_template,
    validate_registration_number,
    validate_grade_remark,
    validate_year,
    validate_age,
    calculate_penalty,
    get_flag_descriptions
)


def extract_birth_year(date_of_birth: str) -> int | None:
    if not date_of_birth:
        return None
    match = re.search(r'\b(19|20)\d{2}\b', str(date_of_birth))
    return int(match.group()) if match else None


def validate_document(file_bytes: bytes, filename: str, selected_cert_type: str) -> dict:
    triggered_flags = []

    # Step 1 — Run Gemini Multimodal Analysis
    response = analyse_certificate(file_bytes, filename, selected_cert_type)
    if not response.get("success") or response.get("type_mismatch"):
        return response

    template = get_template(selected_cert_type)
    gemini_score = response.get("authenticity_score", 0)
    extracted = response.get("extracted_info", {})

    registration_number = extracted.get("registration_number", "")
    exam_year = extracted.get("exam_year", "")
    date_of_birth = extracted.get("date_of_birth", "")
    subject_count = extracted.get("subject_count", 0)
    subjects = extracted.get("subjects", [])

    # Step 2 — Parse numerical years
    try:
        exam_year_int = int(str(exam_year).strip())
    except (ValueError, TypeError):
        exam_year_int = None

    birth_year_int = extract_birth_year(date_of_birth)

    # Step 3 — Deterministic Forensic Checks
    if registration_number and not validate_registration_number(registration_number, selected_cert_type):
        triggered_flags.append("invalid_registration_number")

    if exam_year_int and birth_year_int:
        if not validate_age(birth_year_int, exam_year_int):
            triggered_flags.append("impossible_age")

    if exam_year_int and not validate_year(exam_year_int, selected_cert_type):
        triggered_flags.append("year_out_of_range")

    for subject in subjects:
        grade = subject.get("grade", "")
        remark = subject.get("remark", "")
        if grade and remark:
            if not validate_grade_remark(grade, remark, selected_cert_type):
                triggered_flags.append("grade_remark_mismatch")
                break

    subject_names = [s.get("subject", "").upper() for s in subjects if s.get("subject")]
    if len(subject_names) != len(set(subject_names)):
        triggered_flags.append("duplicate_subjects")

    count_range = template.get("subject_count_range", [8, 9])
    if subject_count and not (count_range[0] <= subject_count <= count_range[1]):
        triggered_flags.append("abnormal_subject_count")

    # Step 4 — Penalty calculation
    total_penalty = calculate_penalty(triggered_flags, selected_cert_type)
    final_score = max(0, gemini_score - total_penalty)

    if final_score >= 75:
        verdict = "AUTHENTIC"
    elif final_score >= 40:
        verdict = "SUSPICIOUS"
    else:
        verdict = "HIGH_RISK"

    flag_details = get_flag_descriptions(triggered_flags, selected_cert_type)

    return {
        "success": True,
        "cert_type": selected_cert_type,
        "gemini_score": gemini_score,
        "total_penalty": total_penalty,
        "document_score": final_score,
        "final_score": final_score,
        "verdict": verdict,
        "triggered_flags": flag_details,
        "extracted_info": extracted,
        "field_checks": response.get("field_checks", {}),
        "flagged_issues": response.get("flagged_issues", []),
        "tampering_signs": response.get("tampering_signs", []),
        "confidence_note": response.get("confidence_note", "")
    }
