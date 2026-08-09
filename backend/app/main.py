from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import coaches, foods, logs, profiles, workouts
from app.core.config import settings
from app.core.rate_limit import limiter

app = FastAPI(title="CalorieParser API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router, prefix="/v1")
app.include_router(foods.router, prefix="/v1")
app.include_router(logs.router, prefix="/v1")
app.include_router(workouts.router, prefix="/v1")
app.include_router(coaches.router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
