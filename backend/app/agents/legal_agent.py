from datetime import datetime
from app.services.ollama_client import OllamaClient


class LegalAgent:
    """Legal Agent — 法务合规【待激活】
    合同条款审查与能源法规问答；激活后接 knowledge_base 做 RAG 增强。
    """

    def __init__(self):
        self.name = "LegalAgent"
        self.description = "合同审查、合规检查、能源法规问答"
        self.client = OllamaClient(model_key="qwen")

    async def run(self, input_data: dict) -> dict:
        review_type = input_data.get("review_type", "通用")
        contract = input_data.get("contract_text", "")
        if not contract:
            return {"status": "error", "error": "缺少 contract_text"}

        system_prompt = f"""你是能源行业法务专家，审查「{review_type}」类合同。

逐条审查并输出：
1. 条款级意见表：条款号 | 内容摘要 | 风险等级(高/中/低) | 问题 | 修改建议
2. 重点检查：价格与结算机制、违约与赔偿上限、不可抗力、期限与续约、
   并网/交付责任划分、知识产权、争议解决方式
3. 缺失条款提示：该类合同应有但文本中缺失的条款
4. 总体意见：可签署 / 修改后签署 / 不建议签署

声明：本意见为 AI 辅助审查，不替代执业律师意见。"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n合同文本：\n{contract[:15000]}"}]

        response = await self.client.chat(messages=messages, temperature=0.1, model_override="qwen")
        if "error" in response:
            return {"status": "error", "error": response["error"]}
        return {"status": "success", "result": response["content"],
                "model": self.client.model, "timestamp": datetime.now().isoformat()}
