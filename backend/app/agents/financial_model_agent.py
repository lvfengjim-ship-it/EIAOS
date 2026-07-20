import os
import json
from datetime import datetime
from app.services.ollama_client import OllamaClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "financial_model")


class FinancialModelAgent:
    """Financial Model — 项目级财务建模 Agent

    职责：基于项目输入参数，构建简化三表逻辑的投资测算，
    输出 IRR / NPV / DSCR / 回收期 + 双因子敏感性矩阵。

    注意：IRR/NPV 由 Python 精确计算（不依赖 LLM 口算），
    LLM 只负责假设合理性校验、结果解读与风险评述。
    """

    def __init__(self):
        self.name = "FinancialModelAgent"
        self.description = "项目财务模型：IRR/NPV/敏感性分析/融资结构测算"
        self.client = OllamaClient(model_key="coder")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---------- 确定性计算（不让 LLM 算数） ----------

    @staticmethod
    def _npv(rate: float, cashflows: list) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))

    @classmethod
    def _irr(cls, cashflows: list, lo=-0.5, hi=1.0, tol=1e-6) -> float:
        for _ in range(200):
            mid = (lo + hi) / 2
            v = cls._npv(mid, cashflows)
            if abs(v) < tol:
                return mid
            if cls._npv(lo, cashflows) * v < 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    def _build_cashflows(self, p: dict) -> dict:
        capex = float(p["capex"])
        life = int(p.get("project_life", 15))
        debt_ratio = float(p.get("debt_ratio", 0.7))
        loan_rate = float(p.get("loan_rate", 0.045))
        loan_years = min(int(p.get("loan_years", 10)), life)

        revenue = p.get("revenue_streams", {})
        annual_revenue = sum(float(v) for v in revenue.values()) if revenue else float(p.get("annual_revenue", 0))
        opex = float(p.get("opex_annual", annual_revenue * 0.05))
        degradation = float(p.get("revenue_degradation", 0.02))  # 年收入年衰减

        debt = capex * debt_ratio
        annual_debt_service = debt * loan_rate / (1 - (1 + loan_rate) ** -loan_years) if loan_years else 0

        equity_cf = [-capex * (1 - debt_ratio)]
        project_cf = [-capex]
        dscr_list = []
        for y in range(1, life + 1):
            rev_y = annual_revenue * (1 - degradation) ** (y - 1)
            ebitda = rev_y - opex
            project_cf.append(ebitda)
            ds = annual_debt_service if y <= loan_years else 0
            if ds > 0:
                dscr_list.append(ebitda / ds)
            equity_cf.append(ebitda - ds)

        payback = next((y for y in range(1, life + 1)
                        if sum(project_cf[:y + 1]) >= 0), None)
        return {
            "project_irr": round(self._irr(project_cf) * 100, 2),
            "equity_irr": round(self._irr(equity_cf) * 100, 2),
            "npv_at_8pct": round(self._npv(0.08, project_cf), 0),
            "payback_years": payback or f">{life}",
            "min_dscr": round(min(dscr_list), 2) if dscr_list else "N/A",
            "annual_revenue_y1": annual_revenue,
            "life": life,
        }

    def _sensitivity(self, p: dict, base_rev: float) -> list:
        rows = []
        for rev_f in (0.8, 0.9, 1.0, 1.1, 1.2):
            row = []
            for util_f in (0.8, 0.9, 1.0, 1.1, 1.2):
                q = dict(p)
                q["annual_revenue"] = base_rev * rev_f * util_f
                q.pop("revenue_streams", None)
                row.append(self._build_cashflows(q)["project_irr"])
            rows.append(row)
        return rows  # [收入系数][利用系数] 的 IRR 矩阵

    # ---------- 主流程 ----------

    async def run(self, input_data: dict) -> dict:
        if "capex" not in input_data:
            return {"status": "error", "error": "缺少必填参数 capex"}

        metrics = self._build_cashflows(input_data)
        sens = self._sensitivity(input_data, metrics["annual_revenue_y1"])

        calc_summary = {
            "输入参数": {k: v for k, v in input_data.items()},
            "核心指标（程序精确计算）": metrics,
            "敏感性矩阵 IRR%（行=收入系数0.8~1.2，列=利用系数0.8~1.2）": sens,
        }

        system_prompt = """你是新能源项目融资建模专家。以下财务指标由程序精确计算，不得修改数字。

你的任务仅限：
1. 假设合理性校验：指出输入假设中明显偏离行业的部分（如 opex 比例、衰减率）
2. 结果解读：IRR/NPV/DSCR 是否达到投资门槛（IRR>8%，DSCR>1.2）
3. 敏感性解读：哪个因子最致命，盈亏平衡点在哪
4. 融资建议：债务比例、期限结构建议
5. 结论：通过 / 有条件通过（列条件）/ 否决

输出 Markdown，数字必须引用程序计算值。"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n{json.dumps(calc_summary, ensure_ascii=False, indent=2)}"}]

        response = await self.client.chat(messages=messages, temperature=0.1, model_override="coder")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        report = (
            f"# 财务模型测算报告\n\n## 程序计算指标\n```json\n"
            f"{json.dumps(metrics, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## 敏感性矩阵（项目IRR%）\n"
            + self._md_table(sens)
            + f"\n\n## 模型解读\n{response['content']}"
        )
        path = self._save(report)

        return {
            "status": "success",
            "metrics": metrics,               # 结构化指标，前端可直接渲染
            "sensitivity": sens,
            "result": response["content"],
            "report_file": path,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def _md_table(sens: list) -> str:
        header = "| 收入\\利用 | 0.8 | 0.9 | 1.0 | 1.1 | 1.2 |\n|---|---|---|---|---|---|"
        rows = [f"| {f} | " + " | ".join(str(v) for v in row) + " |"
                for f, row in zip((0.8, 0.9, 1.0, 1.1, 1.2), sens)]
        return header + "\n" + "\n".join(rows)

    def _save(self, content: str) -> str:
        fname = f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
