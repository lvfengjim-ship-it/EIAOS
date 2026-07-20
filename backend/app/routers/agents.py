from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid

from app.agents.investment_agent import InvestmentScreeningAgent
from app.agents.policy_agent import PolicyAnalysisAgent
from app.agents.market_agent import PowerMarketAgent
from app.agents.audit_agent import FinancialAuditAgent

router = APIRouter()

AGENT_INSTANCES = {
    "investment": InvestmentScreeningAgent(),
    "policy": PolicyAnalysisAgent(),
    "market": PowerMarketAgent(),
    "audit": FinancialAuditAgent(),
}

TASK_STORE = {}

class AgentRunRequest(BaseModel):
    agent_type: str
    input_data: dict

@router.get("/")
async def list_agents():
    return {
        "agents": [
            {
                "id": key,
                "name": agent.name,
                "description": agent.description,
                "model": agent.client.model,
                "status": "available"
            }
            for key, agent in AGENT_INSTANCES.items()
        ]
    }

@router.post("/run")
async def run_agent(request: AgentRunRequest, background_tasks: BackgroundTasks):
    if request.agent_type not in AGENT_INSTANCES:
        available = list(AGENT_INSTANCES.keys())
        raise HTTPException(400, f"未知 Agent: {request.agent_type}。可用: {available}")

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    TASK_STORE[task_id] = {"status": "queued", "agent_type": request.agent_type}

    background_tasks.add_task(execute_agent, task_id, request.agent_type, request.input_data)

    return {"task_id": task_id, "status": "queued"}

async def execute_agent(task_id, agent_type, input_data):
    TASK_STORE[task_id] = {"status": "running", "agent_type": agent_type}

    try:
        agent = AGENT_INSTANCES[agent_type]
        result = await agent.run(input_data)
        TASK_STORE[task_id] = {
            "status": "completed",
            "result": result,
            "model": result.get("model")
        }
    except Exception as e:
        TASK_STORE[task_id] = {"status": "failed", "error": str(e)}

@router.get("/run/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in TASK_STORE:
        raise HTTPException(404, "任务不存在")
    return TASK_STORE[task_id]
