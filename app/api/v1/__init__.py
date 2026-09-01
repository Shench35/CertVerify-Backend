from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payment_router
from app.api.v1.verification import router as verification_router
from app.api.v1.b2b import router as b2b_router
from app.api.v1.admin import router as admin_router

__all__ = ["auth_router", "payment_router", "verification_router", "b2b_router", "admin_router"]
