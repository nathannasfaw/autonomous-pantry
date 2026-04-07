import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Autonomous Pantry", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes.chat import router
app.include_router(router, prefix="/chat")

from app.routes.pantry import router as pantry_router
app.include_router(pantry_router, prefix="/pantry")



# On startup, initialize NN (train or load weights)
from app.services.nn_service import initialize_nn
from app.services.pantry_store import initialize_db


@app.on_event("startup")
async def startup_event():
    initialize_db()
    initialize_nn()
