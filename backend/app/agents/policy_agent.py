from datetime import datetime
from app.services.ollama_client import OllamaClient

class PolicyAnalysisAgent:
    def __init__(self):
        self.name = "PolicyAnalysisAgent"
        self.description = "分析能源政策，生成政策简报"
        self.client = OllamaClient(model_key="qwen")

    async def run(self, input_data: dict) -> dict:
        system_prompt = """你是能源政策研究专家，精通中国能源政策体系。

任务：分析输入的政策文件或政策主题，生成结构化简报。

分析框架：
1. 政策背景：出台原因、政策目标
2. 核心内容：补贴标准、准入条件、时间窗口
3. 影响分析：对储能行业的影响、受益主体
4. 执行要点：申报流程、关键时间节点
5. 风险提示：政策变动风险、执行偏差风险

输出格式：Markdown 结构化简报"""

        content = input_data.get('policy_text', input_data.get('policy_topic', '未提供'))

        messages = [
            {"role": "user", "content": f"{system_prompt}\n\n请分析以下内容：\n{content}"}
        ]

        response = await self.client.chat(
            messages=messages,
            temperature=0.3,
            model_override="qwen"
        )

        return {
            "status": "success",
            "result": response.get("content", ""),
            "model": "qwen3.6:27b",
            "timestamp": datetime.now().isoformat()
        }
