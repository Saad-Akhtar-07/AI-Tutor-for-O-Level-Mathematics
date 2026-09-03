from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import database_lifespan
from .routers.content import router as content_router
from .routers.submissions import router as submissions_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI Mathematics Tutor API",
        version="0.1.0",
        description="Database-backed learning content API for the Probability MVP.",
        lifespan=database_lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    application.include_router(content_router)
    application.include_router(submissions_router)
    return application


app = create_app()
