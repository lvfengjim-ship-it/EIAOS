import os
import json
from datetime import datetime
from app.services.ollama_client import OllamaClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "ems")


class EMSReportAgent:
    """EMS Report — 储能电站运行报告 Agent
    KPI 由程序从遥测数据计算，LLM 负责异常解读与运维建议。
    高频例行任务，默认使用轻量模型（fast）。
    """

    def __init__(self):
        self.name = "EMSReportAgent"
        self.description = "EMS 运行日报/月报：充放电效率、SOC、收益、告警统计"
        self.client = OllamaClient(model_key="fast")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---------- 确定性 KPI 计算 ----------

    @staticmethod
    def _kpis(t: dict) -> dict:
        charge = float(t.get("charge_kwh", 0))
        discharge = float(t.get("discharge_kwh", 0))
        revenue = float(t.get("revenue_yuan", 0))
        capacity = float(t.get("capacity_kwh", 1)) or 1
        alarms = t.get("alarms", [])
        return {
            "充电量_kWh": charge,
            "放电量_kWh": discharge,
            "综合效率_%": round(discharge / charge * 100, 2) if charge else "N/A",
            "等效循环次数": round(discharge / capacity, 3),
            "日收益_元": revenue,
            "单位收益_元每kWh": round(revenue / discharge, 3) if discharge else "N/A",
            "告警总数": len(alarms),
            "严重告警": len([a for a in alarms if str(a.get("level", "")).lower() in ("critical", "严重", "高")]),
        }

    async def run(self, input_data: dict) -> dict:
        station = input_data.get("station_name", "未命名电站")
        date = input_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        telemetry = input_data.get("telemetry", {})

        kpi = self._kpis(telemetry)

        system_prompt = """你是储能电站运维专家。以下 KPI 由程序计算，不得修改数字。

任务：基于 KPI 与原始遥测，输出运行日报的分析部分：
1. 运行评价：效率、循环、收益是否正常（效率正常区间 85-92%）
2. 异常分析：告警聚类、可能根因（BMS/PCS/温控/通信）
3. 收益分析：是否执行了最优充放电策略，偏离多少
4. 明日建议：充放电时段、重点关注设备、是否需要现场巡检
输出 Markdown，简洁，不超过 500 字。"""

        messages = [{"role": "user", "content":
            f"{system_prompt}\n\n电站：{station} 日期：{date}\n"
            f"KPI：{json.dumps(kpi, ensure_ascii=False)}\n"
            f"遥测：{json.dumps(telemetry, ensure_ascii=False)[:6000]}"}]

        response = await self.client.chat(messages=messages, temperature=0.2, model_override="fast")
        if "error" in response:
            return {"status": "error", "error": response["error"]}

        report = (f"# {station} 运行日报（{date}）\n\n## KPI\n"
                  + "\n".join(f"- **{k}**：{v}" for k, v in kpi.items())
                  + f"\n\n## 分析\n{response['content']}")
        path = self._save(report, station, date)

        return {
            "status": "success",
            "kpis": kpi,
            "result": response["content"],
            "report_file": path,
            "model": self.client.model,
            "timestamp": datetime.now().isoformat(),
        }

    def _save(self, content: str, station: str, date: str) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in station)[:30]
        fname = f"ems_{safe}_{date}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
