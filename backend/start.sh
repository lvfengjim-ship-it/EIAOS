#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

# 检查端口占用
PORT=8000
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "端口 $PORT 被占用，正在释放..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo "启动 EIAOS 后端服务..."
echo "API 文档: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
