from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid

from app.services.agent_registry import registry

router = APIRouter()

TASK_STORE = {}


class AgentRunRequest(BaseModel):
    agent_type: str
    input_data: dict


@router.get("/")
async def list_agents():
    """返回全部 11 个 Agent（含 pending），前端据此渲染激活/待激活状态"""
    return {"agents": registry.list_all()}


@router.post("/run")
async def run_agent(request: AgentRunRequest, background_tasks: BackgroundTasks):
    agent, err = registry.get(request.agent_type)
    if err:
        code = 423 if err["error"] == "agent_pending" else 400
        raise HTTPException(code, err)

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    TASK_STORE[task_id] = {"status": "queued", "agent_type": request.agent_type}
    background_tasks.add_task(execute_agent, task_id, request.agent_type, request.input_data)
    return {"task_id": task_id, "status": "queued"}


async def execute_agent(task_id, agent_type, input_data):
    TASK_STORE[task_id] = {"status": "running", "agent_type": agent_type}
    try:
        agent, _ = registry.get(agent_type)
        result = await agent.run(input_data)
        TASK_STORE[task_id] = {
            "status": "completed",
            "result": result,
            "model": result.get("model"),
        }
    except Exception as e:
        TASK_STORE[task_id] = {"status": "failed", "error": str(e)}


@router.get("/run/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in TASK_STORE:
        raise HTTPException(404, "任务不存在")
    return TASK_STORE[task_id]


@router.get("/scheduled")
async def list_scheduled():
    """查看当前启用的定时任务配置"""
    return {"scheduled": registry.scheduled_agents()}
