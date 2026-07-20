"""
定时任务数据源适配层
调度器触发 Agent 前，从这里取输入数据。
返回 None 表示本次跳过（数据源未配置或无新增）。

接入真实数据源时，替换对应函数的实现即可：
  - policy_monitor: 政策 RSS / 政府网站爬虫 / 第三方政策 API
  - power_market:   电力交易平台数据 / 自有采集库
  - ems_report:     电站 EMS 系统 API / InfluxDB / Modbus 采集服务
"""
from datetime import datetime, timedelta
from typing import Optional


def fetch(agent_id: str) -> Optional[dict]:
    provider = {
        "policy_monitor": fetch_policy_items,
        "power_market": fetch_market_data,
        "ems_report": fetch_ems_telemetry,
    }.get(agent_id)
    return provider() if provider else None


def fetch_policy_items() -> Optional[dict]:
    """每日政策扫描数据源。
    TODO: 接入政策源后，返回：
      {"mode": "scan", "policy_items": [{"title": ..., "summary": ..., "url": ..., "date": ...}]}
    """
    return None  # 未配置 → 调度器记录跳过


def fetch_market_data() -> Optional[dict]:
    """每周市场周报数据源。
    TODO: 返回 {"report_type": "weekly", "province": "江苏", "market_data": {...}}
    """
    return None


def fetch_ems_telemetry() -> Optional[dict]:
    """每日 EMS 日报数据源。
    TODO: 返回 {"station_name": ..., "date": 昨日, "telemetry": {...}}
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return None  # 配置后返回含 date=yesterday 的 payload
