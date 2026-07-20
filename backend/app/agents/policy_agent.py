import os
from datetime import datetime
from app.services.ollama_client import OllamaClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "policy")


class PolicyAnalysisAgent:
    """Policy Monitor — 政策监测 Agent
    支持两种模式：
      1. analyze：对单份政策原文/主题做结构化分析（前端手动触发）
      2. scan：每日定时扫描模式，对一批政策摘要做分级筛选，只输出高价值政策
    """

    def __init__(self):
        self.name = "PolicyMonitorAgent"
        self.description = "监测能源政策，生成结构化简报与影响分析"
        self.client = OllamaClient(model_key="qwen")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    async def run(self, input_data: dict) -> dict:
        mode = input_data.get("mode", "analyze")
        if mode == "scan":
            return await self._scan(input_data)
        return await self._analyze(input_data)

    async def _analyze(self, input_data: dict) -> dict:
        system_prompt = """你是能源政策研究专家，精通中国能源政策体系（国家-省-市三级）。

任务：分析输入的政策文件或政策主题，生成结构化简报。

分析框架：
1. 政策背景：出台原因、政策目标、发文层级与效力
2. 核心内容：补贴标准、准入条件、时间窗口、量化指标（逐条提取数字）
3. 影响分析：对储能/新能源投资的影响、受益主体、受损主体
4. 执行要点：申报流程、关键时间节点、所需材料
5. 风险提示：政策变动风险、执行偏差风险、追溯风险
6. 行动建议：对投资平台的具体建议（30/60/90 天）

约束：
- 所有数字必须来自输入材料，不得编造；材料未提及的标注"原文未明确"
- 输出 Markdown 结构化简报"""

        content = input_data.get("policy_text") or input_data.get("policy_topic", "未提供")
        region = input_data.get("region", "")

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n地区限定：{region or '全国'}\n\n请分析以下内容：\n{content}"}]

        response = await self.client.chat(messages=messages, temperature=0.3, model_override="qwen")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        path = self._save(response["content"], prefix="brief")
        return {
            "status": "success",
            "result": response["content"],
            "report_file": path,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    async def _scan(self, input_data: dict) -> dict:
        """每日扫描：输入为政策摘要列表，模型做重要性分级"""
        items = input_data.get("policy_items", [])
        if not items:
            return {"status": "success", "result": "今日无新增政策", "scanned": 0}

        import json
        system_prompt = """你是政策监测筛选器。对输入的政策摘要列表逐条评级：

评级标准：
- A（必须关注）：直接影响储能/新能源项目收益、补贴、准入
- B（值得关注）：行业趋势性、区域性政策
- C（存档即可）：例行通知、与主业弱相关

对每条输出：评级 | 一句话价值判断 | 涉及业务（投资/市场/运营/碳/氢）
最后汇总：A 级政策清单 + 建议深挖的 1-2 条。
只输出评级结果，不要复述原文。"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n今日政策摘要：\n{json.dumps(items, ensure_ascii=False, indent=2)}"}]

        response = await self.client.chat(messages=messages, temperature=0.2, model_override="qwen")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        path = self._save(response["content"], prefix="scan")
        return {
            "status": "success",
            "result": response["content"],
            "scanned": len(items),
            "report_file": path,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    def _save(self, content: str, prefix: str) -> str:
        fname = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
