#!/bin/bash

echo "=== 测试 EIAOS API ==="
echo ""

BASE_URL="http://localhost:8000"

echo "1. 健康检查..."
curl -s $BASE_URL/health | python3 -m json.tool
echo ""

echo "2. 列出 Agents..."
curl -s $BASE_URL/api/agents/ | python3 -m json.tool
echo ""

echo "3. 运行投资分析..."
RESPONSE=$(curl -s -X POST $BASE_URL/api/agents/run   -H "Content-Type: application/json"   -d '{"agent_type":"investment","input_data":{"project_name":"广东储能项目","region":"广东","capacity_mwh":100,"initial_investment":50000000,"annual_revenue":8000000,"project_life":15}}')

echo "$RESPONSE" | python3 -m json.tool
TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
echo ""

echo "4. 等待 5 秒后查询任务状态..."
sleep 5
curl -s $BASE_URL/api/agents/run/$TASK_ID | python3 -m json.tool
echo ""

echo "5. 运行政策分析..."
curl -s -X POST $BASE_URL/api/agents/run   -H "Content-Type: application/json"   -d '{"agent_type":"policy","input_data":{"policy_topic":"2026年新型储能发展政策"}}' | python3 -m json.tool
echo ""

echo "=== 测试完成 ==="
