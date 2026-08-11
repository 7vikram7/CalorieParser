import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import coaches, foods, logs, profiles, workouts
from app.core.config import settings
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

app = FastAPI(title="CalorieParser API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """Catches anything that isn't an HTTPException (i.e. real bugs) and
    turns it into a normal JSON 500 response.

    This can't be done with `@app.exception_handler(Exception)` — Starlette
    special-cases any handler registered for the bare `Exception` type and
    routes it through ServerErrorMiddleware specifically, which sits
    *outside* CORSMiddleware, so responses from it never get CORS headers
    attached (confirmed with Starlette's TestClient: the handled response
    came back correctly, but with no Access-Control-Allow-Origin header at
    all). A middleware added *before* CORSMiddleware below ends up inside it
    in the actual call chain (Starlette's middleware order is reversed from
    registration order), so a response built here still flows out through
    CORSMiddleware's header injection like any other response.

    Without this, an unhandled exception reached the browser as an opaque
    "CORS error" with the real 500 and its message completely invisible in
    the frontend console — this is what made the body_metrics upsert bug
    hard to diagnose from the UI.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(UnhandledExceptionMiddleware)

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
