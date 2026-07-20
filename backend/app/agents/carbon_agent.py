from datetime import datetime
from app.services.ollama_client import OllamaClient

# 全国电网平均排放因子（tCO2/MWh），按生态环境部最新公布值更新
DEFAULT_GRID_FACTOR = 0.5568


class CarbonAgent:
    """Carbon Agent — 碳资产管理【待激活】
    减排量用确定性公式计算，LLM 负责机制适配与申报指引。
    """

    def __init__(self):
        self.name = "CarbonAgent"
        self.description = "碳减排核算、CCER/绿证收益测算、碳市场跟踪"
        self.client = OllamaClient(model_key="gemma4")

    async def run(self, input_data: dict) -> dict:
        gen = float(input_data.get("generation_mwh", 0))
        factor = float(input_data.get("grid_factor", DEFAULT_GRID_FACTOR))
        period = input_data.get("period", "未指定")

        reduction_t = round(gen * factor, 2)   # 减排量 = 电量 × 排放因子

        system_prompt = f"""你是碳资产管理专家。项目周期 {period}，
上网/替代电量 {gen} MWh，电网排放因子 {factor} tCO2/MWh，
程序计算减排量 = {reduction_t} tCO2（不得修改）。

任务：
1. 机制适配：该减排量适用于 CCER / 绿证 / 地方碳普惠 中的哪些，能否叠加
2. 收益测算：按各机制当前合理价格区间给出收益范围（标注"价格假设"）
3. 申报清单：流程步骤、所需材料、监测要求、时间周期
4. 风险提示：额外性论证、重复计算、政策变动
输出 Markdown。"""

        messages = [{"role": "user", "content": system_prompt}]
        response = await self.client.chat(messages=messages, temperature=0.2, model_override="gemma4")
        if "error" in response:
            return {"status": "error", "error": response["error"]}
        return {"status": "success",
                "reduction_tco2": reduction_t,
                "result": response["content"],
                "model": self.client.model, "timestamp": datetime.now().isoformat()}
