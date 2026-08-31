from app.services.template_service import (
    get_template,
    validate_registration_number,
    validate_grade_remark,
    validate_year,
    validate_age,
    calculate_penalty,
    get_flag_descriptions
)


def test_get_waec_template():
    template = get_template("WAEC")
    assert template["issuing_body"] == "West African Examinations Council"
    assert "A1" in template["grade_format"]
    assert template["has_candidate_photo"] is True


def test_get_neco_template():
    template = get_template("NECO")
    assert "National Examinations Council" in template["issuing_body"]
    assert template["registration_number_format"] == r"^\d{10}[A-Z]{2}$"


def test_waec_registration_number_validation():
    assert validate_registration_number("4123456789", "WAEC") is True
    assert validate_registration_number("12345", "WAEC") is False
    assert validate_registration_number("ABC1234567", "WAEC") is False


def test_neco_registration_number_validation():
    assert validate_registration_number("1234567890AB", "NECO") is True
    assert validate_registration_number("1234567890", "NECO") is False


def test_grade_remark_validation():
    assert validate_grade_remark("A1", "EXCELLENT", "NECO") is True
    assert validate_grade_remark("C4", "CREDIT", "NECO") is True
    assert validate_grade_remark("F9", "FAIL", "NECO") is True
    assert validate_grade_remark("A1", "PASS", "NECO") is False


def test_candidate_age_validation():
    assert validate_age(birth_year=2000, exam_year=2018) is True  # Age 18 -> Valid
    assert validate_age(birth_year=2015, exam_year=2018) is False # Age 3 -> Impossible
    assert validate_age(birth_year=1970, exam_year=2018) is False # Age 48 -> Out of range


def test_penalty_and_flag_calculation():
    triggered = ["missing_candidate_photo", "missing_qr_code"]
    penalty = calculate_penalty(triggered, "WAEC")
    assert penalty == 50  # 25 + 25

    descriptions = get_flag_descriptions(triggered, "WAEC")
    assert len(descriptions) == 2
    assert descriptions[0]["severity"] == 25
