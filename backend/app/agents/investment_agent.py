import os
from datetime import datetime
from app.services.ollama_client import OllamaClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "investment")

# 投资硬门槛（与 agents.yaml thresholds 保持一致）
IRR_MIN = 0.08
PAYBACK_MAX = 10


class InvestmentScreeningAgent:
    """Investment Screening — 投资初筛 Agent
    输出综合评分 + 门槛校验 + 是否进入财务建模（financial_model）的建议。
    """

    def __init__(self):
        self.name = "InvestmentScreeningAgent"
        self.description = "储能/新能源项目投资初筛：评分、门槛校验、风险提示"
        self.client = OllamaClient(model_key="gemma4")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    async def run(self, input_data: dict) -> dict:
        system_prompt = f"""你是资深能源投资分析师，拥有15年储能/新能源行业投资经验。

分析维度（逐项打分，满分100）：
1. 财务可行性(30分)：单位投资成本、收入结构、初步回收测算
   硬门槛：IRR > {IRR_MIN:.0%}，回收期 < {PAYBACK_MAX} 年
2. 政策环境(20分)：国家及项目所在省储能政策、补贴退坡风险
3. 市场环境(20分)：峰谷电价差、辅助服务收益、容量租赁市场成熟度
4. 技术风险(15分)：电池技术路线、循环寿命、系统集成商资质
5. 竞争与执行(15分)：区域竞争强度、并网难度、土地合规

输出要求：
- 综合评分(0-100) + 各维度得分
- 门槛校验：明确写出"满足/不满足"及依据
- 结论三选一：【进入深度评估】(≥75) / 【补充材料再审】(60-74) / 【否决】(<60)
- 关键风险 Top5 + 每条一句缓释建议
- 若结论为"进入深度评估"，列出需要 financial_model 复核的参数清单
所有数字必须来自输入或标注"行业经验估计"。"""

        project_info = f"""项目信息：
- 项目名称：{input_data.get('project_name', '未命名')}
- 项目地点：{input_data.get('region', '未知')}
- 储能容量：{input_data.get('capacity_mwh', '未知')} MWh
- 初始投资：{input_data.get('initial_investment', '未知')} 元
- 预计年收入：{input_data.get('annual_revenue', '未知')} 元
- 项目周期：{input_data.get('project_life', '未知')} 年"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n请分析以下项目：\n{project_info}"}]

        response = await self.client.chat(messages=messages, temperature=0.2, model_override="gemma4")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        path = self._save(response["content"], input_data.get("project_name", "unnamed"))
        return {
            "status": "success",
            "result": response["content"],
            "report_file": path,
            "next_step": {
                "condition": "结论为【进入深度评估】时",
                "call": "financial_model",
                "reason": "用确定性计算复核 IRR/NPV/敏感性",
            },
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    def _save(self, content: str, name: str) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in name)[:30]
        fname = f"screen_{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
