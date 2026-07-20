import os
from datetime import datetime
from app.services.ollama_client import OllamaClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "market")


class PowerMarketAgent:
    """Power Market — 电力市场分析 Agent
    支持 report_type: weekly（周报，默认）/ spot_analysis（单次价格分析）/ monthly
    """

    def __init__(self):
        self.name = "PowerMarketAgent"
        self.description = "电力现货/辅助服务市场分析与收益测算"
        self.client = OllamaClient(model_key="gemma4")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    async def run(self, input_data: dict) -> dict:
        report_type = input_data.get("report_type", "weekly")
        province = input_data.get("province", "江苏")
        market_data = input_data.get("market_data", "未提供市场数据")

        system_prompt = f"""你是电力市场分析专家，专注中国电力现货市场和辅助服务市场，熟悉{province}电力交易规则。

任务：生成{report_type}类型的市场分析。

分析维度：
1. 价格分析：日前/实时电价走势、峰谷价差（元/MWh，标注具体数值）
2. 电量分析：交易量、负荷曲线特征、新能源消纳率
3. 辅助服务：调频里程价格、备用价格、调峰补偿 → 储能可参与的收益机会
4. 政策影响：近期政策对市场规则的改变
5. 储能收益测算：基于当前价差，两充两放策略的单位收益（元/kWh/日）
6. 趋势预测：下一周期价格走势及依据

约束：
- 数字必须来自输入数据；数据缺失的维度明确标注"数据不足"
- 对 EMS 运营给出明确的充放电时段建议
输出格式：Markdown 报告"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n市场数据：\n{market_data}"}]

        response = await self.client.chat(messages=messages, temperature=0.3, model_override="gemma4")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        path = self._save(response["content"], report_type)
        return {
            "status": "success",
            "result": response["content"],
            "report_type": report_type,
            "report_file": path,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    def _save(self, content: str, rtype: str) -> str:
        fname = f"{rtype}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
