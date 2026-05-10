from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router as api_router
from core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
	get_settings()
	yield


app = FastAPI(title="FHIR ID Resolve API", version="1.0.0", lifespan=lifespan)
app.include_router(api_router)
