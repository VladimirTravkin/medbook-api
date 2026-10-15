"""API v1 router aggregating all endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, doctors, specializations, users

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(specializations.router)
api_router.include_router(doctors.router)

# Routers will be added here as the API grows:
# from app.api.v1.endpoints import slots, appointments
#
# api_router.include_router(slots.router)
# api_router.include_router(appointments.router)
