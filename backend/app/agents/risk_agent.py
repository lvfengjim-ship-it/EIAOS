from datetime import datetime
from app.services.ollama_client import OllamaClient


class RiskAgent:
    """Risk Agent — 项目全周期风险分析【待激活】
    激活条件见 config/agents.yaml activation_requirements。
    """

    def __init__(self):
        self.name = "RiskAgent"
        self.description = "政策/市场/技术/建设/运营五维风险矩阵与缓释措施"
        self.client = OllamaClient(model_key="qwen")

    async def run(self, input_data: dict) -> dict:
        import json
        focus = input_data.get("risk_focus") or ["政策", "市场", "技术", "建设", "运营"]

        system_prompt = """你是能源项目风险管理专家。对项目做全周期风险评估。

对以下每个维度：识别 3-5 项具体风险，按 概率(1-5)×影响(1-5) 打分：
维度：""" + "、".join(focus) + """

输出：
1. 风险矩阵表（风险描述 | 维度 | 概率 | 影响 | 分值 | 等级）
   等级：分值≥15 红 / 8-14 黄 / <8 绿
2. Top10 风险清单（按分值排序）
3. 每项红/黄风险一句缓释措施
4. 整体风险结论：可承受 / 有条件承受 / 不可承受
不得编造项目数据；信息不足的风险标注"待尽调确认"。"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n项目信息：\n{json.dumps(input_data.get('project_info', {}), ensure_ascii=False, indent=2)}"}]

        response = await self.client.chat(messages=messages, temperature=0.2, model_override="qwen")
        if "error" in response:
            return {"status": "error", "error": response["error"]}
        return {"status": "success", "result": response["content"],
                "model": self.client.model, "timestamp": datetime.now().isoformat()}
