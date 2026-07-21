"""
Financial Model — 项目级财务建模 Agent（v2 大升级）

新增能力（对标台湾 BLPS 表后储能投资平台财模）：
1. 逐年电池衰减曲线：衰减直接驱动收入递减（首年保持率 + 年衰减率，可自定义全表）
2. 四方分润结构：业主/营运商/SPV(投资方)/平台 各自收益与 IRR（比例可配，和为 1）
3. 融资杠杆：贷款比例/利率/期限 → 年金还款计划 → 杠杆后 Equity IRR + DSCR
4. 双敏感性矩阵：
   - 建置成本 × SPV 分润比 → 回收年限（对标 BLPS 成本×分润表）
   - 收入系数 × 利用系数 → 项目 IRR（保留 v1）

原则不变：所有数字由 Python 确定性计算，LLM 只做假设校验与解读。
"""
import os
import json
from datetime import datetime
from app.services.ollama_client import OllamaClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "financial_model")

# 默认电池容量保持率曲线（前 10 年对标 BLPS 实测：98.1% → 84.4%）
DEFAULT_FIRST_YEAR_RETENTION = 0.981
DEFAULT_DEGRADATION = 0.018          # 第 2 年起每年衰减 1.8%
DEFAULT_SHARES = {"owner": 0.15, "operator": 0.15, "spv": 0.65, "platform": 0.05}
PARTY_NAMES = {"owner": "业主", "operator": "营运商", "spv": "SPV投资方", "platform": "平台方"}


class FinancialModelAgent:
    def __init__(self):
        self.name = "FinancialModelAgent"
        self.description = "财务建模 v2：衰减曲线/四方分润/融资杠杆/双敏感性矩阵"
        self.client = OllamaClient(model_key="coder")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---------- 基础工具 ----------

    @staticmethod
    def _npv(rate: float, cashflows: list) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))

    @classmethod
    def _irr(cls, cashflows: list, lo=-0.9, hi=3.0, tol=1e-6):
        f_lo = cls._npv(lo, cashflows)
        if f_lo * cls._npv(hi, cashflows) > 0:
            return None
        for _ in range(300):
            mid = (lo + hi) / 2
            v = cls._npv(mid, cashflows)
            if abs(v) < tol:
                return mid
            if f_lo * v < 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    @staticmethod
    def _payback(cashflows: list):
        cum = 0
        for y, cf in enumerate(cashflows):
            cum += cf
            if cum >= 0 and y > 0:
                return y
        return None

    @staticmethod
    def _annuity(principal: float, rate: float, years: int) -> float:
        if years <= 0:
            return 0.0
        if rate == 0:
            return principal / years
        return principal * rate / (1 - (1 + rate) ** -years)

    # ---------- 参数解析 ----------

    def _parse(self, p: dict) -> dict:
        capex = float(p["capex"])
        life = int(p.get("project_life", 20))

        rev = p.get("revenue_streams")
        y1_revenue = sum(float(v) for v in rev.values()) if rev else float(p.get("annual_revenue", 0))

        shares = {**DEFAULT_SHARES, **p.get("shares", {})}
        total_share = round(sum(shares.values()), 4)
        if abs(total_share - 1.0) > 0.001:
            raise ValueError(f"分润比例之和必须为 1，当前为 {total_share}")

        # 衰减曲线：可用 retention_schedule 完整自定义，否则按参数生成
        schedule = p.get("retention_schedule")
        if schedule:
            retention = [float(x) for x in schedule][:life]
            retention += [retention[-1]] * (life - len(retention))
        else:
            r1 = float(p.get("first_year_retention", DEFAULT_FIRST_YEAR_RETENTION))
            deg = float(p.get("degradation_rate", DEFAULT_DEGRADATION))
            # 第 1 年 100%（新电池），第 2 年起按保持率逐年衰减（对齐 BLPS 实测曲线）
            retention = [1.0] + [r1 * (1 - deg) ** (y - 2) for y in range(2, life + 1)]

        debt_ratio = float(p.get("debt_ratio", 0.0))
        loan_rate = float(p.get("loan_rate", 0.045))
        loan_years = min(int(p.get("loan_years", 10)), life)

        return {
            "capex": capex, "life": life, "y1_revenue": y1_revenue,
            "opex": float(p.get("opex_annual", y1_revenue * 0.02)),
            "insurance": capex * float(p.get("insurance_rate", 0.005)),
            "shares": shares, "retention": retention,
            "debt_ratio": debt_ratio, "loan_rate": loan_rate, "loan_years": loan_years,
            "discount": float(p.get("discount_rate", 0.08)),
        }

    # ---------- 核心计算 ----------

    def _compute(self, cfg: dict) -> dict:
        capex, life = cfg["capex"], cfg["life"]
        spv_share = cfg["shares"]["spv"]

        debt = capex * cfg["debt_ratio"]
        equity = capex - debt
        ds = self._annuity(debt, cfg["loan_rate"], cfg["loan_years"])

        yearly = []
        spv_cf_unlev = [-capex]
        spv_cf_lev = [-equity]
        proj_cf = [-capex]
        dscr_list = []

        for y in range(1, life + 1):
            ret = cfg["retention"][y - 1]
            gross = cfg["y1_revenue"] * ret
            ebitda = gross - cfg["opex"] - cfg["insurance"]
            ds_y = ds if y <= cfg["loan_years"] else 0.0

            spv_gross = gross * spv_share
            spv_net = spv_gross - cfg["opex"] - cfg["insurance"]   # SPV 承担运维与保险
            lev_cf = spv_net - ds_y

            proj_cf.append(ebitda)
            spv_cf_unlev.append(spv_net)
            spv_cf_lev.append(lev_cf)
            if ds_y > 0 and spv_net > 0:
                dscr_list.append(spv_net / ds_y)

            yearly.append({
                "year": y, "retention_pct": round(ret * 100, 1),
                "gross_revenue": round(gross, 0), "ebitda": round(ebitda, 0),
                "debt_service": round(ds_y, 0),
                "spv_income": round(spv_net, 0), "spv_levered_cf": round(lev_cf, 0),
                **{f"{k}_income": round(gross * cfg["shares"][k], 0)
                   for k in ("owner", "operator", "platform")},
            })

        # 其他三方：零投资纯分成
        parties = {}
        for k in ("owner", "operator", "platform"):
            incomes = [cfg["y1_revenue"] * cfg["retention"][y - 1] * cfg["shares"][k]
                       for y in range(1, life + 1)]
            parties[k] = {
                "name": PARTY_NAMES[k], "share": cfg["shares"][k],
                "year1_income": round(incomes[0], 0),
                "total_income": round(sum(incomes), 0),
                "note": "零投资纯分成，无 IRR",
            }

        unlev_irr = self._irr(spv_cf_unlev)
        lev_irr = self._irr(spv_cf_lev) if cfg["debt_ratio"] > 0 else None
        proj_irr = self._irr(proj_cf)

        return {
            "yearly": yearly,
            "project": {
                "capex": capex, "life_years": life,
                "year1_revenue": cfg["y1_revenue"],
                "irr_unlevered_pct": round(proj_irr * 100, 2) if proj_irr else None,
                "npv_pct": round(self._npv(cfg["discount"], proj_cf), 0),
                "discount_rate": cfg["discount"],
            },
            "spv": {
                "share": spv_share,
                "unlevered": {
                    "investment": capex,
                    "irr_pct": round(unlev_irr * 100, 2) if unlev_irr else None,
                    "payback_years": self._payback(spv_cf_unlev) or f">{life}",
                    "total_net": round(sum(spv_cf_unlev), 0),
                },
                "levered": {
                    "debt_ratio": cfg["debt_ratio"], "loan_rate": cfg["loan_rate"],
                    "loan_years": cfg["loan_years"],
                    "equity": round(equity, 0), "annual_debt_service": round(ds, 0),
                    "equity_irr_pct": round(lev_irr * 100, 2) if lev_irr else None,
                    "equity_payback_years": (self._payback(spv_cf_lev) or f">{life}") if cfg["debt_ratio"] > 0 else None,
                    "min_dscr": round(min(dscr_list), 2) if dscr_list else None,
                },
            },
            "parties": parties,
            "_cf": {"proj": proj_cf, "unlev": spv_cf_unlev, "lev": spv_cf_lev},  # 供敏感性复用
        }

    # ---------- 敏感性矩阵 ----------

    def _sens_capex_share(self, p: dict, cfg: dict) -> dict:
        """建置成本 × SPV 分润比 → SPV 回收年限（对标 BLPS 成本×分润表）"""
        capex_factors = [0.85, 0.925, 1.0, 1.075, 1.15]
        share_levels = [0.55, 0.60, 0.65, 0.70, 0.75]
        base_capex = cfg["capex"]
        rows = []
        for share in share_levels:
            row = []
            for f in capex_factors:
                q = dict(p)
                q["capex"] = base_capex * f
                q["shares"] = {**cfg["shares"], "spv": share}
                # 重归一化：spv 变化从 owner/operator 等比扣减
                rest = 1 - share - q["shares"]["platform"]
                orig_rest = cfg["shares"]["owner"] + cfg["shares"]["operator"]
                q["shares"]["owner"] = round(rest * cfg["shares"]["owner"] / orig_rest, 4)
                q["shares"]["operator"] = round(rest - q["shares"]["owner"], 4)
                try:
                    c = self._parse(q)
                    r = self._compute(c)
                    row.append(r["spv"]["unlevered"]["payback_years"])
                except Exception:
                    row.append("-")
            rows.append(row)
        return {"row_label": "SPV分润比", "col_label": "建置成本系数",
                "rows": share_levels, "cols": capex_factors,
                "values": rows, "metric": "回收年限(年)"}

    def _sens_rev_util(self, p: dict, cfg: dict) -> dict:
        """收入系数 × 利用系数 → 项目 IRR%（保留 v1 维度）"""
        levels = [0.8, 0.9, 1.0, 1.1, 1.2]
        rows = []
        for rf in levels:
            row = []
            for uf in levels:
                cf = [-cfg["capex"]]
                for y in range(1, cfg["life"] + 1):
                    gross = cfg["y1_revenue"] * cfg["retention"][y - 1] * rf * uf
                    cf.append(gross - cfg["opex"] - cfg["insurance"])
                irr = self._irr(cf)
                row.append(round(irr * 100, 2) if irr else "-")
            rows.append(row)
        return {"row_label": "收入系数", "col_label": "利用系数",
                "rows": levels, "cols": levels, "values": rows, "metric": "项目IRR(%)"}

    # ---------- 报告渲染 ----------

    @staticmethod
    def _md_matrix(sens: dict) -> str:
        header = f"| {sens['row_label']}＼{sens['col_label']} | " + \
                 " | ".join(str(c) for c in sens["cols"]) + " |"
        sep = "|" + "---|" * (len(sens["cols"]) + 1)
        lines = [f"**{sens['metric']}**", "", header, sep]
        for r, vals in zip(sens["rows"], sens["values"]):
            lines.append(f"| {r} | " + " | ".join(str(v) for v in vals) + " |")
        return "\n".join(lines)

    def _render_tables(self, result: dict, s1: dict, s2: dict) -> str:
        spv, proj = result["spv"], result["project"]
        L = []
        L.append("## 核心指标\n")
        L.append("| 指标 | 数值 |")
        L.append("|---|---|")
        L.append(f"| 总投资 | {proj['capex']:,.0f} 元 |")
        L.append(f"| 首年收入 | {proj['year1_revenue']:,.0f} 元 |")
        L.append(f"| 项目 IRR（无杠杆） | {proj['irr_unlevered_pct']}% |")
        L.append(f"| NPV@{proj['discount_rate']:.0%} | {proj['npv_pct']:,.0f} 元 |")
        u = spv["unlevered"]
        L.append(f"| SPV 无杠杆 IRR | {u['irr_pct']}%（回收 {u['payback_years']} 年） |")
        lv = spv["levered"]
        if lv["equity_irr_pct"] is not None:
            L.append(f"| SPV 杠杆后 Equity IRR | **{lv['equity_irr_pct']}%**（自有资金 {lv['equity']:,.0f} 元，回收 {lv['equity_payback_years']} 年） |")
            L.append(f"| 最低 DSCR | {lv['min_dscr']} |")
        L.append("")
        L.append("## 四方分润（按年衰减累计）\n")
        L.append("| 方 | 比例 | 首年收益 | 全周期累计 | 说明 |")
        L.append("|---|---|---|---|---|")
        for k in ("owner", "operator", "spv", "platform"):
            if k == "spv":
                L.append(f"| SPV投资方 | {spv['share']:.0%} | — | {u['total_net']:,.0f} | 承担投资/运维/保险 |")
            else:
                pt = result["parties"][k]
                L.append(f"| {pt['name']} | {pt['share']:.0%} | {pt['year1_income']:,.0f} | {pt['total_income']:,.0f} | {pt['note']} |")
        L.append("")
        L.append("## 逐年现金流（前 10 年）\n")
        L.append("| 年 | 电池保持率 | 总收入 | EBITDA | 还本付息 | SPV净收益(无杠杆) | SPV现金流(杠杆) |")
        L.append("|---|---|---|---|---|---|---|")
        for y in result["yearly"][:10]:
            L.append(f"| {y['year']} | {y['retention_pct']}% | {y['gross_revenue']:,.0f} "
                     f"| {y['ebitda']:,.0f} | {y['debt_service']:,.0f} "
                     f"| {y['spv_income']:,.0f} | {y['spv_levered_cf']:,.0f} |")
        L.append("\n## 敏感性矩阵一：建置成本 × SPV 分润比\n")
        L.append(self._md_matrix(s1))
        L.append("\n## 敏感性矩阵二：收入 × 利用率\n")
        L.append(self._md_matrix(s2))
        return "\n".join(L)

    # ---------- 主流程 ----------

    async def run(self, input_data: dict) -> dict:
        if "capex" not in input_data:
            return {"status": "error", "error": "缺少必填参数 capex"}
        try:
            cfg = self._parse(input_data)
        except ValueError as e:
            return {"status": "error", "error": str(e)}

        result = self._compute(cfg)
        sens1 = self._sens_capex_share(input_data, cfg)
        sens2 = self._sens_rev_util(input_data, cfg)
        tables = self._render_tables(result, sens1, sens2)

        llm_input = {
            "输入参数": {k: v for k, v in input_data.items()},
            "核心指标": {"项目": result["project"], "SPV": result["spv"],
                        "其他方": result["parties"]},
        }
        system_prompt = """你是新能源项目投资总监。以下财务指标由程序精确计算（含逐年电池衰减、四方分润、融资杠杆），不得修改数字。

你的任务仅限：
1. 假设校验：衰减曲线、分润比例、贷款条件是否偏离行业常态
2. 投资门槛判断：无杠杆 IRR>8%？杠杆后 Equity IRR 是否达到对应资金方门槛
   （平台投资方>15% / 基建基金>10% / 险资>8%）？DSCR>1.2？
3. 结构建议：分润比例与融资结构是否有优化空间
4. 结论：通过 / 有条件通过（列条件）/ 否决
输出 Markdown，简洁，所有数字引用程序计算值。"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n{json.dumps(llm_input, ensure_ascii=False, indent=2)}"}]

        response = await self.client.chat(messages=messages, temperature=0.1, model_override="coder")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        report = f"# 财务模型测算报告 v2\n\n{tables}\n\n## 投资总监解读\n{response['content']}"
        path = self._save(report)

        result.pop("_cf", None)
        return {
            "status": "success",
            "metrics": {"project": result["project"], "spv": result["spv"],
                        "parties": result["parties"]},
            "yearly": result["yearly"],
            "sensitivity": {"capex_share": sens1, "revenue_util": sens2},
            "result": f"{tables}\n\n---\n\n{response['content']}",
            "report_file": path,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    def _save(self, content: str) -> str:
        fname = f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
