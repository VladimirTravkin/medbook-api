"""API v1 router aggregating all endpoint modules."""

from fastapi import APIRouter

api_router = APIRouter()

# Routers will be added here as the API grows:
# from app.api.v1.endpoints import auth, users, doctors, slots, appointments
#
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
# api_router.include_router(slots.router, prefix="/slots", tags=["slots"])
# api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
