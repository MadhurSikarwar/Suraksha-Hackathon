import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import document, graph, audit, metrics
from app.models.audit_log import init_db

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Suraksha: Document Fraud Detection API",
    description="Multimodal AI pipeline for detecting forged Indian property documents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — restrict in production to your frontend domain
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Register routers
app.include_router(document.router, prefix="/api/v1/document", tags=["Document Analysis"])
app.include_router(graph.router,    prefix="/api/v1/graph",    tags=["Graph Intelligence"])
app.include_router(audit.router,    prefix="/api/v1/audit",    tags=["Audit & Compliance"])
app.include_router(metrics.router,  prefix="/api/v1/metrics",  tags=["Performance Metrics"])

# Serve generated heatmap images as static files
os.makedirs("static/heatmaps", exist_ok=True)
os.makedirs("temp_uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize the audit database and log startup."""
    init_db()
    logger.info("Suraksha API started successfully.")


@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": "Suraksha API is running.",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Root"])
def health_check():
    """
    Health check endpoint used by Docker and load balancers.
    Returns 200 OK when the service is ready.
    """
    return {"status": "healthy", "service": "suraksha-backend"}
