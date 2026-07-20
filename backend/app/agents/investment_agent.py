from datetime import datetime
from app.services.ollama_client import OllamaClient

class InvestmentScreeningAgent:
    def __init__(self):
        self.name = "InvestmentScreeningAgent"
        self.description = "评估储能项目的投资价值"
        self.client = OllamaClient(model_key="gemma4")

    async def run(self, input_data: dict) -> dict:
        system_prompt = """你是资深能源投资分析师，拥有15年储能行业投资经验。

分析维度：
1. 财务指标：IRR(要求>8%)、NPV(要求>0)、投资回收期(要求<10年)
2. 政策环境：国家储能政策、地方补贴、电力市场化改革
3. 市场环境：峰谷电价差、辅助服务收益、容量租赁
4. 技术风险：电池技术路线、循环寿命、系统集成
5. 竞争格局：区域竞争强度、进入壁垒

输出：综合评分(0-100)、投资建议、关键风险、优化建议"""

        project_info = f"""项目信息：
- 项目名称：{input_data.get('project_name', '未命名')}
- 项目地点：{input_data.get('region', '未知')}
- 储能容量：{input_data.get('capacity_mwh', '未知')} MWh
- 初始投资：{input_data.get('initial_investment', '未知')} 元
- 预计年收入：{input_data.get('annual_revenue', '未知')} 元
- 项目周期：{input_data.get('project_life', '未知')} 年"""

        messages = [
            {"role": "user", "content": f"{system_prompt}\n\n请分析以下项目：\n{project_info}"}
        ]

        response = await self.client.chat(
            messages=messages,
            temperature=0.2,
            model_override="gemma4"
        )

        if "error" in response:
            return {"status": "error", "error": response["error"]}

        return {
            "status": "success",
            "result": response["content"],
            "model": "gemma4:31b",
            "timestamp": datetime.now().isoformat()
        }
