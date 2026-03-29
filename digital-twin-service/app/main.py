from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Digital Twin Service", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)
app.include_router(router)
