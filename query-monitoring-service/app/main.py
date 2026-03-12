from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Read-only service — tables are owned and created by the write services
    yield


app = FastAPI(title="Query Monitoring Service", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)
app.include_router(router)