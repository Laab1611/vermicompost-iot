from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router
from app.database.base import Base
from app.database.connection import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Telemetry Ingestion Service", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)
app.include_router(router)