import os
import json
from datetime import datetime
from app.services.ollama_client import OllamaClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "gis")

# 默认因子权重（可在 input 中用 weights 覆盖）
DEFAULT_WEIGHTS = {
    "resource": 0.30,    # 风光资源（辐照/风速/利用小时）
    "grid": 0.25,        # 电网接入（距变电站、消纳空间、接入批复难度）
    "land": 0.20,        # 土地（性质合规、租金、面积匹配、地质）
    "policy": 0.15,      # 地方政策（补贴、准入、生态红线）
    "economy": 0.10,     # 经济性（建设成本、运输、地方电价）
}


class GISSiteSelectionAgent:
    """GIS Site Selection — 选址评估 Agent
    多因子加权评分由程序计算，LLM 负责因子打分依据与排除项判断。
    """

    def __init__(self):
        self.name = "GISSiteSelectionAgent"
        self.description = "基于资源/电网/土地/政策多因子加权的选址评分"
        self.client = OllamaClient(model_key="gemma4")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    async def run(self, input_data: dict) -> dict:
        sites = input_data.get("candidate_sites", [])
        ptype = input_data.get("project_type", "储能")
        weights = {**DEFAULT_WEIGHTS, **input_data.get("weights", {})}

        if not sites:
            return {"status": "error", "error": "缺少 candidate_sites"}

        system_prompt = f"""你是新能源项目选址专家，项目类型：{ptype}。

对输入的每个候选地块，按以下 5 个因子分别打分（0-10）并给一句依据：
- resource(资源) / grid(电网接入) / land(土地) / policy(政策) / economy(经济性)

硬性排除项（命中即 total=0，标注排除原因）：
- 位于生态红线/基本农田/水源地保护区
- 土地性质不符且无法变更
- 距最近变电站 > 30km（储能）或消纳空间为零

输出 JSON（只输出 JSON，不要多余文字）：
[{{"site": "名称", "scores": {{"resource": x, "grid": x, "land": x, "policy": x, "economy": x}},
   "excluded": false, "exclude_reason": "", "notes": "关键依据"}}]"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n候选地块：\n{json.dumps(sites, ensure_ascii=False, indent=2)}"}]

        response = await self.client.chat(messages=messages, temperature=0.2, model_override="gemma4")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        ranked = self._rank(response["content"], weights)

        report = self._render_report(ranked, ptype, weights)
        path = self._save(report)
        return {
            "status": "success",
            "ranking": ranked,
            "result": report,
            "report_file": path,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    def _rank(self, llm_output: str, weights: dict) -> list:
        """解析 LLM 因子分，用确定性权重加权"""
        try:
            txt = llm_output.strip()
            start, end = txt.find("["), txt.rfind("]") + 1
            scored = json.loads(txt[start:end])
        except Exception:
            return [{"site": "解析失败", "raw": llm_output[:500]}]

        for s in scored:
            if s.get("excluded"):
                s["total"] = 0
            else:
                s["total"] = round(sum(
                    s.get("scores", {}).get(k, 0) * w for k, w in weights.items()
                ), 2)
        return sorted(scored, key=lambda x: x.get("total", 0), reverse=True)

    def _render_report(self, ranked: list, ptype: str, weights: dict) -> str:
        lines = [f"# {ptype}项目选址评估报告",
                 f"\n权重：{json.dumps(weights, ensure_ascii=False)}\n",
                 "| 排名 | 地块 | 总分 | 资源 | 电网 | 土地 | 政策 | 经济 | 备注 |",
                 "|---|---|---|---|---|---|---|---|---|"]
        for i, s in enumerate(ranked, 1):
            sc = s.get("scores", {})
            note = s.get("exclude_reason") or s.get("notes", "")
            lines.append(
                f"| {i} | {s.get('site')} | {s.get('total')} | {sc.get('resource','-')} "
                f"| {sc.get('grid','-')} | {sc.get('land','-')} | {sc.get('policy','-')} "
                f"| {sc.get('economy','-')} | {note} |")
        if ranked and ranked[0].get("total", 0) > 0:
            lines.append(f"\n**推荐地块：{ranked[0]['site']}**（总分 {ranked[0]['total']}）")
            lines.append("建议下一步：推荐地块进入 investment_screening 投资初筛。")
        return "\n".join(lines)

    def _save(self, content: str) -> str:
        fname = f"site_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
