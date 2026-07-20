from datetime import datetime
from app.services.ollama_client import OllamaClient

class FinancialAuditAgent:
    def __init__(self):
        self.name = "FinancialAuditAgent"
        self.description = "基于财务报表出具审计意见"
        self.client = OllamaClient(model_key="coder")

    async def run(self, input_data: dict) -> dict:
        system_prompt = """你是资深财务总监，拥有20年审计经验。

任务：基于提供的财务报表数据，出具审计意见。

分析维度：
1. 资产负债表：资产结构、负债率、流动性
2. 利润表：收入质量、毛利率、费用控制
3. 现金流量表：经营现金流、投资现金流、筹资现金流
4. 关键指标：ROE、ROA、流动比率、速动比率
5. 异常识别：关联交易、大额往来、异常波动

输出格式：
- 审计意见（无保留/保留/否定）
- 关键发现
- 风险提示
- 改进建议"""

        import json
        financial_data = json.dumps(input_data.get('financial_data', {}), ensure_ascii=False, indent=2)

        messages = [
            {"role": "user", "content": f"{system_prompt}\n\n请审计以下财务数据：\n{financial_data}"}
        ]

        response = await self.client.chat(
            messages=messages,
            temperature=0.1,
            model_override="coder"
        )

        return {
            "status": "success",
            "result": response.get("content", ""),
            "model": "qwen3-coder:30b",
            "timestamp": datetime.now().isoformat()
        }
