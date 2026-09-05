import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.routers import analytics, audit, cart, chat, demo, orders, payments, products, webhooks

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("paypilot")

app = FastAPI(
    title="PayPilot AI",
    description="An explainable, bounded AI shopping agent for agentic commerce on Razorpay.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    from app.seed import run as seed_run
    seed_run()
    logger.info("PayPilot AI backend started. Razorpay mock mode: %s", not settings.razorpay_configured)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak internals/secrets in error responses; log server-side only.
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "razorpay_mock_mode": not settings.razorpay_configured,
        "agent_llm_configured": settings.agent_llm_configured,
    }


app.include_router(products.router)
app.include_router(cart.router)
app.include_router(chat.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(webhooks.router)
app.include_router(audit.router)
app.include_router(analytics.router)
app.include_router(demo.router)
