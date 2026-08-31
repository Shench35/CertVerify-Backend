import re

REFERENCE_TEMPLATES = {
    "WAEC": {
        "full_name": "West African Senior School Certificate",
        "issuing_body": "West African Examinations Council",
        "exam_types": ["WASSCE (SC)", "WASSCE (PC)", "GCE"],
        "registration_number_format": r"^\d{10}$",
        "certificate_number_format": r"^NGWASSCS\s?\d+$",
        "required_fields": [
            "candidate_name", "date_of_birth", "sex", "school_name",
            "subject_results_table", "subject_count", "candidate_number",
            "certificate_number", "chairman_signature", "registrar_signature",
            "waec_seal", "qr_code", "candidate_photo", "SUBJECT RECORDED"
        ],
        "required_text_markers": [
            "West African Examinations Council",
            "This is to Certify that",
            "whose photograph is embossed",
            "having been in attendance at",
            "Chairman of Council",
            "Registrar to Council",
            "Any alteration, erasure or absence of photograph renders this Certificate invalid"
        ],
        "grade_format": ["A1", "B2", "B3", "C4", "C5", "C6", "D7", "E8", "F9"],
        "subject_count_range": [8, 9],
        "layout": {
            "candidate_photo_position": "top right",
            "qr_code_position": "bottom center",
            "waec_seal_position": "bottom center right",
            "chairman_signature_position": "bottom right",
            "registrar_signature_position": "far bottom right",
            "candidate_number_position": "bottom left",
            "border": "decorative blue border all around"
        },
        "colour_scheme": "Cream/yellow background with blue decorative border",
        "has_watermark": True,
        "has_qr_code": True,
        "has_candidate_photo": True,
        "valid_year_range": [1990, 2026],
        "red_flags": {
            "missing_candidate_photo": {"severity": 25, "description": "Candidate photo is missing"},
            "missing_qr_code": {"severity": 25, "description": "QR code is missing"},
            "missing_chairman_signature": {"severity": 35, "description": "Chairman signature is missing"},
            "missing_registrar_signature": {"severity": 35, "description": "Registrar signature is missing"},
            "invalid_candidate_number": {"severity": 40, "description": "Candidate number is not 10 digits"},
            "invalid_certificate_number": {"severity": 40, "description": "Certificate number format invalid"},
            "missing_disclaimer_text": {"severity": 20, "description": "Disclaimer text at bottom is missing"},
            "invalid_grade_format": {"severity": 30, "description": "Subject grades not in format A1-F9"},
            "missing_school_name": {"severity": 20, "description": "School name is missing"},
            "missing_date_of_birth": {"severity": 20, "description": "Date of birth is missing"},
            "missing_sex_field": {"severity": 15, "description": "Sex field is missing"},
            "missing_waec_seal": {"severity": 35, "description": "WAEC seal is missing or pixelated"},
            "missing_border": {"severity": 20, "description": "Blue decorative border is missing or altered"},
            "font_inconsistency": {"severity": 25, "description": "Font inconsistency detected"},
            "subject_count_mismatch": {"severity": 30, "description": "Subject count mismatch"},
            "abnormal_subject_count": {"severity": 20, "description": "Subject count outside normal 8-9 range"},
            "missing_issuing_body_text": {"severity": 40, "description": "Issuing body header text is missing"},
            "year_out_of_range": {"severity": 35, "description": "Certificate year is outside valid range"},
            "impossible_age": {"severity": 45, "description": "Candidate age is impossible given birth year and exam year"},
            "duplicate_subjects": {"severity": 30, "description": "Duplicate subjects found in results table"}
        }
    },
    "NECO": {
        "full_name": "Senior School Certificate Examination",
        "issuing_body": "National Examinations Council (NECO)",
        "exam_types": ["SSCE", "GCE"],
        "registration_number_format": r"^\d{10}[A-Z]{2}$",
        "school_number_format": r"^\d{7}$",
        "required_fields": [
            "candidate_name", "registration_number", "exam_year", "exam_type",
            "school_number", "school_name", "gender", "date_of_birth",
            "subject_results_table", "candidate_photo", "qr_code"
        ],
        "required_text_markers": [
            "FEDERAL REPUBLIC OF NIGERIA",
            "NATIONAL EXAMINATIONS COUNCIL",
            "NECO",
            "SENIOR SCHOOL CERTIFICATE EXAMINATION",
            "Candidate's Name",
            "Registration Number",
            "Exam Year",
            "Exam Type",
            "School Number",
            "School Name",
            "This Result is provisional",
            "This Result is not transferable",
            "National Examinations Council (NECO)"
        ],
        "results_table_columns": ["S/N", "SUBJECT", "GRADE", "REMARK"],
        "grade_format": ["A1", "B2", "B3", "C4", "C5", "C6", "D7", "E8", "F9"],
        "remark_format": ["EXCELLENT", "VERY GOOD", "GOOD", "CREDIT", "PASS", "FAIL"],
        "exam_type_values": ["INTERNAL", "EXTERNAL"],
        "subject_count_range": [8, 9],
        "grade_remark_mapping": {
            "A1": "EXCELLENT", "B2": "VERY GOOD", "B3": "GOOD",
            "C4": "CREDIT", "C5": "CREDIT", "C6": "CREDIT",
            "D7": "PASS", "E8": "PASS", "F9": "FAIL"
        },
        "layout": {
            "header": "centered - FEDERAL REPUBLIC OF NIGERIA at top",
            "coat_of_arms": "center top below header",
            "candidate_photo_position": "top right",
            "results_table": "center with S/N, SUBJECT, GRADE, REMARK columns",
            "qr_code_position": "bottom right of notes section",
            "copyright_position": "very bottom center"
        },
        "colour_scheme": "White background, black text, Nigeria coat of arms",
        "has_watermark": False,
        "has_qr_code": True,
        "has_candidate_photo": True,
        "valid_year_range": [1999, 2026],
        "red_flags": {
            "missing_federal_republic_header": {"severity": 40, "description": "FEDERAL REPUBLIC OF NIGERIA header is missing"},
            "missing_coat_of_arms": {"severity": 35, "description": "Nigeria coat of arms is missing"},
            "invalid_registration_number": {"severity": 40, "description": "Registration number should be 10 digits followed by 2 letters"},
            "invalid_school_number": {"severity": 30, "description": "School number should be 7 digits"},
            "missing_candidate_photo": {"severity": 25, "description": "Candidate photo is missing"},
            "missing_qr_code": {"severity": 25, "description": "QR code is missing"},
            "missing_remark_column": {"severity": 30, "description": "Results table is missing REMARK column"},
            "invalid_grade_format": {"severity": 30, "description": "Grade not in format A1-F9"},
            "grade_remark_mismatch": {"severity": 35, "description": "Remark does not match expected grade value"},
            "missing_exam_type": {"severity": 25, "description": "Exam type field is missing"},
            "invalid_exam_type": {"severity": 30, "description": "Exam type is not INTERNAL or EXTERNAL"},
            "missing_note_section": {"severity": 20, "description": "NOTE section is missing"},
            "missing_copyright_line": {"severity": 20, "description": "Copyright line is missing"},
            "invalid_date_format": {"severity": 20, "description": "Date of birth not in valid date format"},
            "missing_gender": {"severity": 15, "description": "Gender field is missing"},
            "year_out_of_range": {"severity": 35, "description": "Certificate year is outside valid range"},
            "impossible_age": {"severity": 45, "description": "Candidate age is impossible given birth year and exam year"},
            "duplicate_subjects": {"severity": 30, "description": "Duplicate subjects found in results table"},
            "abnormal_subject_count": {"severity": 20, "description": "Subject count outside normal range of 8-9"}
        }
    }
}


def get_template(cert_type: str) -> dict:
    cert_type_upper = cert_type.upper()
    if any(k in cert_type_upper for k in ["WAEC", "WASSCE", "GCE"]):
        return REFERENCE_TEMPLATES["WAEC"]
    elif any(k in cert_type_upper for k in ["NECO", "SSCE"]):
        return REFERENCE_TEMPLATES["NECO"]
    return REFERENCE_TEMPLATES["WAEC"]


def validate_registration_number(number: str, cert_type: str) -> bool:
    template = get_template(cert_type)
    pattern = template.get("registration_number_format", "")
    if not pattern or not number:
        return True
    return bool(re.match(pattern, number.strip()))


def validate_grade_remark(grade: str, remark: str, cert_type: str) -> bool:
    template = get_template(cert_type)
    mapping = template.get("grade_remark_mapping", {})
    if not mapping or not grade or not remark:
        return True
    expected_remark = mapping.get(grade.upper(), "")
    return expected_remark == remark.upper()


def validate_year(year: int, cert_type: str) -> bool:
    if not year:
        return True
    template = get_template(cert_type)
    valid_range = template.get("valid_year_range", [1990, 2026])
    return valid_range[0] <= year <= valid_range[1]


def validate_age(birth_year: int, exam_year: int) -> bool:
    if not birth_year or not exam_year:
        return True
    age_at_exam = exam_year - birth_year
    return 14 <= age_at_exam <= 25


def calculate_penalty(triggered_flags: list[str], cert_type: str) -> int:
    template = get_template(cert_type)
    red_flags = template.get("red_flags", {})
    total_penalty = 0
    for flag in triggered_flags:
        if flag in red_flags:
            total_penalty += red_flags[flag]["severity"]
    return total_penalty


def get_flag_descriptions(triggered_flags: list[str], cert_type: str) -> list[dict]:
    template = get_template(cert_type)
    red_flags = template.get("red_flags", {})
    descriptions = []
    for flag in triggered_flags:
        if flag in red_flags:
            descriptions.append({
                "flag": flag,
                "severity": red_flags[flag]["severity"],
                "description": red_flags[flag]["description"]
            })
    return sorted(descriptions, key=lambda x: x["severity"], reverse=True)
