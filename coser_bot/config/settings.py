"""
@description: 设置配置模块，存储系统配置参数
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础路径设置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# 数据库路径
DATABASE_PATH = os.path.join(DATA_DIR, os.getenv("DATABASE_PATH", "coser_bot.db"))

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# 日志设置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(LOG_DIR, "coser_bot.log")

# 机器人设置
BOT_TOKEN = "7637865854:AAHEGsy5VoMlhSLug1tdt-2kXnVE_D7weAk"
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# 签到积分设置
DAILY_CHECKIN_POINTS = 10  # 每日签到基础积分
WEEKLY_STREAK_POINTS = 20  # 连续签到7天额外奖励
MONTHLY_STREAK_POINTS = 100  # 连续签到30天额外奖励
CHECKIN_COOLDOWN_HOURS = 24  # 签到冷却时间（小时）

# 补签设置
MAKEUP_CHECKIN_ENABLED = True  # 是否启用补签功能
MAKEUP_CHECKIN_COST = 50  # 每天补签消耗的积分
MAKEUP_CHECKIN_MAX_DAYS = 3  # 最多可补签的天数
MAKEUP_CHECKIN_MONTHLY_LIMIT = 1  # 每月补签次数限制

# 积分赠送设置
GIFT_POINTS_ENABLED = True  # 是否启用积分赠送功能
GIFT_POINTS_MIN = 10  # 最小赠送积分数
GIFT_POINTS_MAX = 1000  # 最大赠送积分数
GIFT_POINTS_DAILY_LIMIT = 500  # 每日赠送积分上限
GIFT_POINTS_FEE_RATE = 0.05  # 赠送积分手续费率（5%）

# 邮箱验证设置
EMAIL_VERIFICATION_ENABLED = True  # 是否启用邮箱验证
EMAIL_VERIFICATION_BONUS = 50  # 邮箱验证奖励积分
EMAIL_VERIFICATION_EXPIRY_MINUTES = 5  # 邮箱验证码有效期（分钟）
EMAIL_VERIFICATION_COOLDOWN_DAYS = 30  # 邮箱更改冷却期（天）
MIN_POINTS_FOR_EMAIL_BINDING = 5  # 绑定邮箱所需最低积分

# 群组设置
GROUP_ACCESS_CHECK_INTERVAL = 24  # 群组访问权限检查间隔（小时）
GROUP_REMINDER_BEFORE_EXPIRY_DAYS = 3  # 到期前提醒天数

# SMTP设置（用于发送验证邮件）
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Coser Bot")

# 数据备份设置
AUTO_BACKUP_ENABLED = True  # 是否启用自动备份
AUTO_BACKUP_INTERVAL_HOURS = 24  # 自动备份间隔（小时）
MAX_BACKUP_COUNT = 30  # 最大备份保留数量

# 性能设置
CACHE_EXPIRY_SECONDS = 300  # 缓存过期时间（秒）
DB_CONNECTION_TIMEOUT = 10  # 数据库连接超时（秒）

# 安全设置
MAX_LOGIN_ATTEMPTS = 5  # 最大登录尝试次数
LOGIN_COOLDOWN_MINUTES = 30  # 登录冷却时间（分钟）

# 调试设置
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# 积分赠送相关设置
GIFT_EXPIRY_HOURS = 24  # 积分赠送过期时间（小时）
MIN_GIFT_AMOUNT = 1     # 最小赠送积分数量
MAX_GIFT_AMOUNT = 100000  # 最大赠送积分数量

# 恢复请求配置
RECOVERY_REQUEST_EXPIRY_DAYS = 7  # 恢复请求有效期（天）
RECOVERY_COOLDOWN_DAYS = 30  # 同一邮箱恢复冷却期（天）
MAX_RECOVERY_ATTEMPTS_PER_DAY = 3  # 每日最大恢复尝试次数

# 日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "level": LOG_LEVEL,
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILE,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "standard",
            "encoding": "utf8",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
    },
} 