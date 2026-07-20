from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import agents

app = FastAPI(title="EIAOS", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api/agents", tags=["agents"])


@app.on_event("startup")
async def startup_event():
    try:
        from app.services.scheduler import start_scheduler
        app.state.scheduler = start_scheduler()
    except ImportError:
        # apscheduler 未安装时跳过定时任务，不影响 API
        print("[EIAOS] apscheduler 未安装，定时任务未启动。pip install apscheduler")


@app.on_event("shutdown")
async def shutdown_event():
    sched = getattr(app.state, "scheduler", None)
    if sched:
        sched.shutdown(wait=False)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "EIAOS Backend", "version": "1.1.0"}


TASK_STORE = agents.TASK_STORE
