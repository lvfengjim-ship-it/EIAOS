"""
定时调度器：按 agents.yaml 中 schedule.cron 自动触发 Agent。
依赖：apscheduler（已加入 requirements.txt）

当前启用的定时任务：
  policy_monitor  — 每天 08:00 政策扫描（需提供 policy_items 数据源）
  power_market    — 每周一 09:00 市场周报（需提供 market_data 数据源）
  ems_report      — 每天 07:00 运行日报（需提供 telemetry 数据源）

注意：定时触发需要数据源。data_providers.py 负责从外部拉取数据，
在接入真实数据源前，调度器会记录"跳过：无数据源"日志而不报错。
"""
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("eiaos.scheduler")
logging.basicConfig(level=logging.INFO)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_job(agent_id: str):
    def job():
        from app.services.agent_registry import registry
        try:
            from app.services import data_providers
            payload = data_providers.fetch(agent_id)
        except ImportError:
            payload = None

        if payload is None:
            logger.info(f"[{agent_id}] 定时触发：无数据源（data_providers 未配置），本次跳过")
            return

        agent, err = registry.get(agent_id)
        if err:
            logger.warning(f"[{agent_id}] 定时触发失败：{err}")
            return

        result = _run_async(agent.run(payload))
        logger.info(f"[{agent_id}] 定时任务完成：{result.get('status')}, "
                    f"报告：{result.get('report_file', '-')}")
    return job


def start_scheduler():
    from app.services.agent_registry import registry
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    count = 0
    for item in registry.scheduled_agents():
        agent_id = item["id"]
        cron = item["schedule"].get("cron")
        if not cron:
            continue
        minute, hour, day, month, dow = cron.split()
        scheduler.add_job(
            _make_job(agent_id),
            CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow),
            id=agent_id, replace_existing=True,
        )
        count += 1
        logger.info(f"已注册定时任务：{agent_id}  cron: {cron}")
    scheduler.start()
    logger.info(f"调度器启动，共 {count} 个定时任务")
    return scheduler
