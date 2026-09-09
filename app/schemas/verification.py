from enum import Enum
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class CertificateType(str, Enum):
    WAEC = "WAEC"
    NECO = "NECO"


class AnalyseResponse(BaseModel):
    success: bool
    transaction_ref: Optional[str] = None
    final_trust_score: Optional[float] = None
    final_verdict: Optional[str] = None
    document_score: Optional[float] = None
    flagged_issues: list[str] = []
    triggered_flags: list[dict] = []
    tampering_signs: list[str] = []
    extracted_info: dict[str, Any] = {}
    confidence_note: Optional[str] = None
    message: str
    type_mismatch: Optional[bool] = None
    detected_type: Optional[str] = None
    error: Optional[str] = None


class VerificationHistoryItem(BaseModel):
    transaction_ref: str
    cert_type: Optional[CertificateType] = None
    created_at: datetime
    document_score: Optional[float] = None
    final_trust_score: Optional[float] = None
    final_verdict: Optional[str] = None


class VerificationReportResponse(BaseModel):
    transaction_ref: str
    cert_type: Optional[CertificateType] = None
    created_at: datetime
    document_score: Optional[float] = None
    final_trust_score: Optional[float] = None
    final_verdict: Optional[str] = None
    extracted_info: dict[str, Any] = {}
    flagged_issues: list[str] = []
    triggered_flags: list[dict] = []
    tampering_signs: list[str] = []
