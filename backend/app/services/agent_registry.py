"""
Agent 注册表加载器
从 backend/config/agents.yaml 读取全部 Agent 配置，
按 status 动态实例化 active Agent，pending Agent 返回待激活提示。
"""
import os
import yaml
import importlib
from typing import Dict, Any, Optional


CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "agents.yaml"
)


class AgentRegistry:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        self.instances: Dict[str, Any] = {}
        self.metadata: Dict[str, dict] = {}
        self._instantiate_agents()

    def _load_config(self) -> dict:
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _instantiate_agents(self):
        for agent_id, cfg in self.config.get("agents", {}).items():
            self.metadata[agent_id] = cfg
            if cfg.get("status") != "active":
                continue  # pending 的不实例化，省内存
            try:
                module = importlib.import_module(cfg["module"])
                cls = getattr(module, cfg["class"])
                self.instances[agent_id] = cls()
            except Exception as e:
                print(f"[Registry] Agent {agent_id} 实例化失败: {e}")

    def get(self, agent_id: str):
        """返回 (instance, error_dict)。pending/未知时 instance 为 None"""
        if agent_id not in self.metadata:
            return None, {
                "error": "unknown_agent",
                "message": f"未知 Agent: {agent_id}",
                "available": list(self.metadata.keys()),
            }
        if agent_id not in self.instances:
            cfg = self.metadata[agent_id]
            return None, {
                "error": "agent_pending",
                "message": f"「{cfg.get('name_zh', agent_id)}」尚未激活",
                "activation_requirements": cfg.get("activation_requirements", []),
                "hint": "将 backend/config/agents.yaml 中该 Agent 的 status 改为 active 并重启后端",
            }
        return self.instances[agent_id], None

    def list_all(self) -> list:
        result = []
        for agent_id, cfg in self.metadata.items():
            inst = self.instances.get(agent_id)
            result.append({
                "id": agent_id,
                "name": cfg.get("name"),
                "name_zh": cfg.get("name_zh"),
                "description": cfg.get("description"),
                "status": cfg.get("status"),
                "model": getattr(getattr(inst, "client", None), "model", None),
                "model_key": cfg.get("model_key"),
                "schedule": cfg.get("schedule", {}),
                "input_schema": cfg.get("input_schema", {}),
                "activation_requirements": cfg.get("activation_requirements"),
            })
        return result

    def scheduled_agents(self) -> list:
        """返回所有启用定时任务的 active Agent，供调度器使用"""
        return [
            {"id": aid, "schedule": cfg["schedule"]}
            for aid, cfg in self.metadata.items()
            if cfg.get("status") == "active"
            and cfg.get("schedule", {}).get("enabled")
        ]


# 全局单例
registry = AgentRegistry()
