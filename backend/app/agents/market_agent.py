from datetime import datetime
from app.services.ollama_client import OllamaClient

class PowerMarketAgent:
    def __init__(self):
        self.name = "PowerMarketAgent"
        self.description = "分析电力市场数据，生成周报"
        self.client = OllamaClient(model_key="gemma4")

    async def run(self, input_data: dict) -> dict:
        system_prompt = """你是电力市场分析专家，专注于中国电力现货市场和辅助服务市场。

任务：分析电力市场数据，生成市场周报。

分析维度：
1. 价格分析：日前/实时电价走势、峰谷价差
2. 电量分析：交易量、负荷曲线、新能源消纳
3. 辅助服务：调频、备用、调峰收益
4. 政策影响：新出台政策对市场的影响
5. 趋势预测：下周价格走势预测

输出格式：Markdown 周报格式"""

        market_data = input_data.get('market_data', '未提供市场数据')

        messages = [
            {"role": "user", "content": f"{system_prompt}\n\n请分析以下市场数据：\n{market_data}"}
        ]

        response = await self.client.chat(
            messages=messages,
            temperature=0.3,
            model_override="gemma4"
        )

        return {
            "status": "success",
            "result": response.get("content", ""),
            "model": "gemma4:31b",
            "timestamp": datetime.now().isoformat()
        }
