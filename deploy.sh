#!/bin/bash
# Coser社群机器人部署脚本 - 宝塔版

# 显示彩色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}开始部署 Coser社群机器人...${NC}"

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${YELLOW}检测到Python版本: ${python_version}${NC}"

# 设置项目目录
PROJECT_DIR=$(pwd)
echo -e "${YELLOW}项目目录: ${PROJECT_DIR}${NC}"

# 检查并安装必要的包
echo -e "${YELLOW}检查并安装必要的包...${NC}"
python3 -m pip install -r requirements.txt

# 检查.env文件是否存在
if [ ! -f .env ]; then
    echo -e "${RED}错误: .env 文件不存在!${NC}"
    if [ -f .env.example ]; then
        echo -e "${YELLOW}从示例创建.env文件...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}已创建.env文件，请编辑并填写必要的配置信息${NC}"
    else
        echo -e "${RED}错误：.env.example文件也不存在！${NC}"
        exit 1
    fi
fi

# 创建必要的目录
echo -e "${YELLOW}创建必要的目录...${NC}"
mkdir -p data logs backups

# 设置权限
echo -e "${YELLOW}设置目录权限...${NC}"
chmod -R 755 ${PROJECT_DIR}
chmod -R 777 logs data backups

# 备份旧数据库(如果存在)
if [ -f coser_bot.db ]; then
    echo -e "${YELLOW}备份现有数据库...${NC}"
    timestamp=$(date +%Y%m%d_%H%M%S)
    cp coser_bot.db backups/coser_bot_${timestamp}.db
fi

# 检查是否有旧的进程在运行
pid=$(ps -ef | grep "python3 simple_bot.py" | grep -v grep | awk '{print $2}')
if [ ! -z "$pid" ]; then
    echo -e "${YELLOW}发现旧的机器人进程 (PID: $pid), 正在停止...${NC}"
    kill $pid
    sleep 2
fi

# 更新systemd服务文件
echo -e "${YELLOW}更新systemd服务配置...${NC}"
cat > /www/server/panel/plugin/supervisor/conf/coser-bot.ini << EOF
[program:coser-bot]
command=python3 ${PROJECT_DIR}/simple_bot.py
directory=${PROJECT_DIR}
user=www
autostart=true
autorestart=true
startsecs=10
startretries=3
redirect_stderr=true
stdout_logfile=${PROJECT_DIR}/logs/supervisor_stdout.log
stderr_logfile=${PROJECT_DIR}/logs/supervisor_stderr.log
environment=PYTHONUNBUFFERED="1"
EOF

# 重启supervisor服务
echo -e "${YELLOW}重启supervisor服务...${NC}"
supervisorctl update
supervisorctl restart coser-bot

# 检查是否成功启动
sleep 5
if supervisorctl status coser-bot | grep -q "RUNNING"; then
    echo -e "${GREEN}机器人已成功启动!${NC}"
    echo -e "${YELLOW}日志文件位于: logs/supervisor_stdout.log${NC}"
    echo -e "${YELLOW}使用以下命令查看日志:${NC}"
    echo -e "${YELLOW}  tail -f logs/supervisor_stdout.log${NC}"
else
    echo -e "${RED}机器人启动失败，请检查日志文件获取详细信息${NC}"
    echo -e "${YELLOW}  cat logs/supervisor_stderr.log${NC}"
fi

echo -e "${GREEN}部署完成!${NC}" 