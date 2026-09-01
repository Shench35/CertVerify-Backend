from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payment_router
from app.api.v1.verification import router as verification_router
from app.api.v1.b2b import router as b2b_router
from app.api.v1.admin import router as admin_router

api_router = APIRouter()

# Primary V1 API Endpoints
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(payment_router, prefix="/payment", tags=["Payments"])
api_router.include_router(verification_router, prefix="/AI_pipeline/verify", tags=["AI Verification"])
api_router.include_router(b2b_router, prefix="/third_party/api/v1", tags=["B2B API Integration"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin Panel"])
