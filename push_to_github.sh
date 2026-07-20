#!/bin/bash
cd ~/EIAOS

echo "=== 推送到 GitHub ==="

# 检查是否是 git 仓库
if [ ! -d ".git" ]; then
    echo "初始化 Git 仓库..."
    git init
    git remote add origin https://github.com/lvfengjim-ship-it/EIAOS.git
fi

# 添加所有更改
git add index.html agents.js backend/ frontend/ data/ deploy_eiaos.sh test_api.sh start.sh requirements.txt .env.example

# 查看状态
echo ""
echo "Git 状态:"
git status

# 提交
echo ""
read -p "输入提交信息 (默认: Update AI Agent platform): " msg
msg=${msg:-"Update AI Agent platform"}
git commit -m "$msg"

# 推送
echo ""
echo "正在推送..."
git push origin main

echo ""
echo "✓ 推送完成!"
