"""
FastAPI application setup: create app, register routes, set up middleware.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import init_db
from app.api.routes import health, documents, query, evaluate, companies
from app.core.config import BACKEND_HOST, BACKEND_PORT


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="ESG Evaluation RAG Backend API")

    # Enable CORS for the frontend reverse proxy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Startup event: initialize database
    @app.on_event("startup")
    async def startup_event():
        """Initialize database on startup."""
        init_db()

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "ESG Evaluation RAG Backend API", "status": "running"}

    # Register routers
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(query.router)
    app.include_router(evaluate.router)
    app.include_router(companies.router)

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)
