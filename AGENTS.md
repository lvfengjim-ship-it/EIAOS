# EIAOS Agent 系统说明

能源投资运营平台（EIAOS）多 Agent 架构，运行于 **Mac Studio 64GB + Ollama 本地模型**。

## 架构总览

```
前端 (index.html + frontend/js/agents_ext.js)
   │  POST /api/agents/run  {agent_type, input_data}
   ▼
FastAPI 路由 (backend/app/routers/agents.py)
   │  按 agent_type 查询注册表
   ▼
Agent 注册表 (backend/app/services/agent_registry.py)
   │  读取 backend/config/agents.yaml
   │  active → 实例化执行；pending → 返回 423 + 激活指引
   ▼
11 个 Agent (backend/app/agents/*.py)
   │  确定性计算用 Python；推理/生成用 Ollama
   ▼
Ollama 本地模型 (backend/app/services/ollama_client.py)
```

**核心设计原则：LLM 不做计算。** IRR/NPV/LCOH/加权评分/KPI 等数字一律由 Python
精确计算，LLM 只负责假设校验、解读、建议——避免大模型口算错误。

## Agent 清单

| ID | 模块 | 状态 | 模型 | 触发方式 |
|---|---|---|---|---|
| `policy_monitor` | 政策监测 | ✅ active | qwen | 手动 + 每日 08:00 定时 |
| `investment_screening` | 投资筛选 | ✅ active | gemma4 | 手动 |
| `financial_model` | 财务建模 | ✅ active | coder | 手动（初筛通过后调用） |
| `gis_site_selection` | GIS 选址 | ✅ active | gemma4 | 手动 |
| `power_market` | 电力市场 | ✅ active | gemma4 | 手动 + 每周一 09:00 定时 |
| `ems_report` | EMS 运行报告 | ✅ active | fast | 手动 + 每日 07:00 定时 |
| `knowledge_base` | 知识库 | ✅ active | qwen + embedding | 手动（其他 Agent 可写入） |
| `risk_agent` | 风险分析 | ⏸ pending | qwen | 手动 |
| `legal_agent` | 法务合规 | ⏸ pending | qwen | 手动 |
| `carbon_agent` | 碳资产 | ⏸ pending | gemma4 | 手动 |
| `hydrogen_agent` | 氢能 | ⏸ pending | gemma4 | 手动 |

## 调用链

```
gis_site_selection ──推荐地块──▶ investment_screening ──进入深度评估──▶ financial_model
policy_monitor ──政策入库──▶ knowledge_base ◀──报告归档── power_market / ems_report
investment_screening ──项目信息──▶ risk_agent（激活后）
```

## 部署步骤

```bash
# 1. 准备模型（首次）
ollama pull gemma4:31b
ollama pull qwen3.6:27b        # 按 ollama list 实际名称调整
ollama pull qwen3-coder:30b
ollama pull nemotron-3-nano:30b
ollama pull nomic-embed-text   # knowledge_base 向量化

# 2. 安装依赖
cd backend && source venv/bin/activate
pip install -r requirements.txt

# 3. 启动
./start.sh        # http://localhost:8000/docs
```

## 激活 pending Agent

1. 确认 `agents.yaml` 中该 Agent 的 `activation_requirements` 已满足
2. 将 `status: pending` 改为 `status: active`
3. 重启后端。前端按钮自动从"待激活"变为可点击

## 定时任务

由 `app/services/scheduler.py`（APScheduler）按 `agents.yaml` 的 cron 触发。
触发前从 `app/services/data_providers.py` 取数据；该文件是数据源适配层，
接入真实政策源/电力交易数据/EMS API 时只需修改对应函数。未配置时定时任务
记录"跳过"日志，不会报错。

## 输出目录

所有报告落盘在 `backend/outputs/<模块>/`（已加入 .gitignore，不入库）。
`knowledge_base` 的向量库存于 `backend/outputs/knowledge/vector_store.json`。

## 模型分配说明

| model_key | 模型 | 分配理由 |
|---|---|---|
| gemma4 | gemma4:31b | 通用分析与报告生成 |
| qwen | qwen3.6:27b | 中文政策/法律长文本理解 |
| coder | qwen3-coder:30b | 计算密集与结构化输出 |
| fast | nemotron-3-nano:30b | 高频例行任务（EMS 日报） |
