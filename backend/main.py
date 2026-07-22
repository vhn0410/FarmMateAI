from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from fastapi.middleware.cors import CORSMiddleware
from app.infrastructure.db.init_db import initialize_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database automatically (create tables if needed, without deleting data)
    initialize_database()
    yield
    # Cleanup (if needed to release resources)

# Initialize the FastAPI application
app = FastAPI(
    title="FarmMate AI API",
    description="Agricultural AI advisory backend system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow the frontend to call from any port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the full v1 router in the main application
# The outer prefix is /api/v1
app.include_router(api_router, prefix="/api/v1")


# A small API to check whether the server is running
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend FarmMate AI is running!"}
