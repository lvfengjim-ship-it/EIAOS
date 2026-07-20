from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import agents

app = FastAPI(title="EIAOS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api/agents", tags=["agents"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "EIAOS Backend"}

TASK_STORE = agents.TASK_STORE
