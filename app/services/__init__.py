"""
Services package encapsulating all business logic, AI pipelines, forensic analysis, payments, and external integrations.
"""
from app.services.template_service import get_template
from app.services.document_analyser import analyse_certificate
from app.services.validator_service import validate_document
from app.services.assessment_service import generate_questions, evaluate_answers
from app.services.auth_service import register_user, login_user, refresh_access_token, send_password_reset_email, get_user_profile
from app.services.b2b_service import create_b2b_key, deduct_b2b_credit, add_b2b_credits, get_b2b_key_data, get_b2b_balance, get_user_b2b_keys

__all__ = [
    "get_template",
    "analyse_certificate",
    "validate_document",
    "generate_questions",
    "evaluate_answers",
    "register_user",
    "login_user",
    "refresh_access_token",
    "send_password_reset_email",
    "get_user_profile",
    "create_b2b_key",
    "deduct_b2b_credit",
    "add_b2b_credits",
    "get_b2b_key_data",
    "get_b2b_balance",
    "get_user_b2b_keys",
]
