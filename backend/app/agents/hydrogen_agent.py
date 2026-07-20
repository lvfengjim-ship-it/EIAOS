from datetime import datetime
from app.services.ollama_client import OllamaClient


class HydrogenAgent:
    """Hydrogen Agent — 绿氢项目评估【待激活】
    LCOH 核心项程序计算，LLM 做技术路线对比与耦合策略。
    """

    def __init__(self):
        self.name = "HydrogenAgent"
        self.description = "绿氢项目评估：LCOH 测算、电解槽选型、风光氢耦合"
        self.client = OllamaClient(model_key="gemma4")

    @staticmethod
    def _lcoh(p: dict) -> dict:
        mw = float(p.get("electrolyzer_mw", 1))
        hours = float(p.get("annual_hours", 4000))
        price = float(p.get("electricity_price", 0.3))      # 元/kWh
        kwh_per_kg = float(p.get("kwh_per_kg", 55))          # 电耗
        capex_per_kw = float(p.get("capex_per_kw", 4000))    # 电解槽单位投资
        life = int(p.get("life_years", 15))

        annual_kg = mw * 1000 * hours / kwh_per_kg
        elec_cost = kwh_per_kg * price
        annual_capex = mw * 1000 * capex_per_kw / life
        capex_cost = annual_capex / annual_kg if annual_kg else 0
        return {
            "年产氢_kg": round(annual_kg, 0),
            "电费成本_元每kg": round(elec_cost, 2),
            "折旧成本_元每kg": round(capex_cost, 2),
            "LCOH下限_元每kg": round(elec_cost + capex_cost, 2),
        }

    async def run(self, input_data: dict) -> dict:
        import json
        p = input_data.get("project_info", {})
        lcoh = self._lcoh(p)

        system_prompt = f"""你是氢能项目评估专家。程序计算的 LCOH 核心构成（不得修改）：
{json.dumps(lcoh, ensure_ascii=False)}

任务：
1. 技术路线对比：ALK / PEM / AEM 在本项目规模下的适配性
2. 耦合策略：与风光出力曲线匹配的运行策略、储能缓冲配置
3. 消纳路径：就近工业用氢 / 加氢站 / 掺氢 / 化工原料，各路径门槛
4. 政策：绿氢补贴与示范项目申报窗口
5. 结论：LCOH 与目标售价对比，是否具备经济性
输出 Markdown。"""

        messages = [{"role": "user", "content": system_prompt}]
        response = await self.client.chat(messages=messages, temperature=0.3, model_override="gemma4")
        if "error" in response:
            return {"status": "error", "error": response["error"]}
        return {"status": "success", "lcoh": lcoh, "result": response["content"],
                "model": self.client.model, "timestamp": datetime.now().isoformat()}
