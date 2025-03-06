"""
配置类模块
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

class Config:
    # 加载环境变量
    load_dotenv()

    # 基础路径设置
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    BACKUP_DIR = os.path.join(BASE_DIR, "backups")
    LOG_DIR = os.path.join(BASE_DIR, "logs")

    # 确保目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # 日志设置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.path.join(LOG_DIR, "coser_bot.log")

    # 机器人设置
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

    # 积分设置
    DAILY_CHECKIN_POINTS = 10
    WEEKLY_STREAK_POINTS = 50
    MONTHLY_STREAK_POINTS = 200

# 创建配置实例
config = Config() 