"""
@description: 独立启动脚本，用于启动Coser社群Bot
"""
import os
import sys
import logging
import asyncio
from pathlib import Path
from datetime import datetime, date
import traceback
import random
import string
import re
from typing import Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

# 设置事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    # 导入必要的库
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram import Update, Bot
    from dotenv import load_dotenv
    
    # 加载环境变量
    load_dotenv()
    
    # 基础配置
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("未设置BOT_TOKEN环境变量，请检查.env文件")
    
    ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
    DATABASE_PATH = os.getenv("DATABASE_PATH", "coser_bot.db")
    LOG_PATH = os.getenv("LOG_PATH", "logs")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # 签到积分配置
    DAILY_CHECKIN_POINTS = 10
    WEEKLY_STREAK_POINTS = 20
    MONTHLY_STREAK_POINTS = 100
    
    # 配置日志
    log_dir = Path(LOG_PATH)
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"coser_bot_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    # 设置第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    
    # 定义常量和数据模型
    class PointsTransactionType(Enum):
        CHECKIN = "签到"
        STREAK_BONUS = "连续签到奖励"
        GIFT_SENT = "赠送积分"
        GIFT_RECEIVED = "收到积分"
        ADMIN_ADJUSTMENT = "管理员调整"
    
    # 回复模板
    TEMPLATES = {
        "checkin_success": """
✅ 签到成功！
👤 用户：@{username}
💰 获得积分：{points}
📈 当前积分：{total_points}
📆 连续签到：{streak_days}天
🎯 下次额外奖励：还需{days_to_next_reward}天(+{next_reward_points}积分)
""",
        "checkin_streak_bonus": """
🎉 签到成功！
👤 用户：@{username}
💰 基础积分：{base_points}
🎁 连续签到{streak_days}天奖励：+{bonus_points}
📈 当前积分：{total_points}
📆 连续签到：{streak_days}天
🎯 下次额外奖励：还需{days_to_next_reward}天(+{next_reward_points}积分)
""",
        "checkin_monthly_bonus": """
🌟 签到成功！
👤 用户：@{username}
💰 基础积分：{base_points}
🏆 连续签到30天奖励：+{bonus_points}
📈 当前积分：{total_points}
📆 连续签到：{streak_days}天
✨ 太棒了！你已经连续签到一个月啦！
""",
        "checkin_already": """
⚠️ 今天已经签到过啦！
📅 明天再来吧~
"""
    }
    
    @dataclass
    class User:
        """用户数据模型"""
        user_id: int
        username: str
        join_date: datetime = field(default_factory=datetime.now)
        points: int = 0
        frozen_points: int = 0
        email: Optional[str] = None
        email_verified: bool = False
        last_email_change: Optional[datetime] = None
        last_checkin_date: Optional[date] = None
        streak_days: int = 0
        total_checkins: int = 0
        monthly_checkins: int = 0
        makeup_chances: int = 1
    
    @dataclass
    class PointsTransaction:
        """积分交易数据模型"""
        user_id: int
        amount: int
        transaction_type: PointsTransactionType
        description: str
        created_at: datetime = field(default_factory=datetime.now)
        related_user_id: Optional[int] = None
        transaction_id: Optional[int] = None
    
    @dataclass
    class CheckinRecord:
        """签到记录数据模型"""
        user_id: int
        checkin_date: date
        points_earned: int
        streak_bonus: int = 0
        created_at: datetime = field(default_factory=datetime.now)
        record_id: Optional[int] = None
    
    # 辅助函数
    def format_number(number: int) -> str:
        """格式化数字，添加千位分隔符"""
        return f"{number:,}"
    
    # 数据库操作
    import aiosqlite
    
    class Database:
        """数据库操作类"""
        
        def __init__(self, db_path: str = DATABASE_PATH):
            self.db_path = db_path
            self.connection = None
        
        async def connect(self) -> None:
            """连接数据库"""
            try:
                self.connection = await aiosqlite.connect(self.db_path)
                self.connection.row_factory = aiosqlite.Row
                logger.info(f"数据库连接成功: {self.db_path}")
            except Exception as e:
                logger.error(f"数据库连接失败: {e}")
                raise
        
        async def disconnect(self) -> None:
            """断开数据库连接"""
            if self.connection:
                await self.connection.close()
                logger.info("数据库连接已关闭")
        
        async def initialize(self) -> None:
            """初始化数据库表"""
            if not self.connection:
                await self.connect()
            
            # 创建用户表
            await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                join_date TIMESTAMP,
                points INTEGER DEFAULT 0,
                frozen_points INTEGER DEFAULT 0,
                email TEXT,
                email_verified BOOLEAN DEFAULT 0,
                last_email_change TIMESTAMP,
                last_checkin_date DATE,
                streak_days INTEGER DEFAULT 0,
                total_checkins INTEGER DEFAULT 0,
                monthly_checkins INTEGER DEFAULT 0,
                makeup_chances INTEGER DEFAULT 1
            )
            """)
            
            # 创建积分交易表
            await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS points_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                transaction_type TEXT,
                description TEXT,
                created_at TIMESTAMP,
                related_user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """)
            
            # 创建签到记录表
            await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS checkin_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                checkin_date DATE,
                points_earned INTEGER,
                streak_bonus INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """)
            
            await self.connection.commit()
            logger.info("数据库表初始化完成")
        
        async def get_user(self, user_id: int) -> Optional[User]:
            """获取用户信息"""
            async with self.connection.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(
                        user_id=row['user_id'],
                        username=row['username'],
                        join_date=datetime.fromisoformat(row['join_date']) if row['join_date'] else datetime.now(),
                        points=row['points'],
                        frozen_points=row['frozen_points'],
                        email=row['email'],
                        email_verified=bool(row['email_verified']),
                        last_email_change=datetime.fromisoformat(row['last_email_change']) if row['last_email_change'] else None,
                        last_checkin_date=date.fromisoformat(row['last_checkin_date']) if row['last_checkin_date'] else None,
                        streak_days=row['streak_days'],
                        total_checkins=row['total_checkins'],
                        monthly_checkins=row['monthly_checkins'],
                        makeup_chances=row['makeup_chances']
                    )
                return None
        
        async def create_user(self, user: User) -> None:
            """创建新用户"""
            await self.connection.execute(
                """
                INSERT INTO users (
                    user_id, username, join_date, points, frozen_points,
                    email, email_verified, last_email_change,
                    last_checkin_date, streak_days, total_checkins,
                    monthly_checkins, makeup_chances
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id, user.username, user.join_date.isoformat(),
                    user.points, user.frozen_points, user.email,
                    user.email_verified, user.last_email_change.isoformat() if user.last_email_change else None,
                    user.last_checkin_date.isoformat() if user.last_checkin_date else None,
                    user.streak_days, user.total_checkins, user.monthly_checkins,
                    user.makeup_chances
                )
            )
            await self.connection.commit()
            logger.info(f"创建新用户: {user.user_id} - {user.username}")
        
        async def update_user(self, user: User) -> None:
            """更新用户信息"""
            await self.connection.execute(
                """
                UPDATE users SET
                    username = ?,
                    points = ?,
                    frozen_points = ?,
                    email = ?,
                    email_verified = ?,
                    last_email_change = ?,
                    last_checkin_date = ?,
                    streak_days = ?,
                    total_checkins = ?,
                    monthly_checkins = ?,
                    makeup_chances = ?
                WHERE user_id = ?
                """,
                (
                    user.username, user.points, user.frozen_points,
                    user.email, user.email_verified,
                    user.last_email_change.isoformat() if user.last_email_change else None,
                    user.last_checkin_date.isoformat() if user.last_checkin_date else None,
                    user.streak_days, user.total_checkins, user.monthly_checkins,
                    user.makeup_chances, user.user_id
                )
            )
            await self.connection.commit()
            logger.debug(f"更新用户信息: {user.user_id} - {user.username}")
        
        async def add_points_transaction(self, transaction: PointsTransaction) -> int:
            """添加积分交易记录"""
            cursor = await self.connection.execute(
                """
                INSERT INTO points_transactions (
                    user_id, amount, transaction_type, description,
                    created_at, related_user_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.user_id, transaction.amount,
                    transaction.transaction_type.value, transaction.description,
                    transaction.created_at.isoformat(),
                    transaction.related_user_id
                )
            )
            await self.connection.commit()
            transaction_id = cursor.lastrowid
            logger.info(f"添加积分交易: ID={transaction_id}, 用户={transaction.user_id}, 金额={transaction.amount}")
            return transaction_id
        
        async def add_checkin_record(self, record: CheckinRecord) -> int:
            """添加签到记录"""
            cursor = await self.connection.execute(
                """
                INSERT INTO checkin_records (
                    user_id, checkin_date, points_earned, streak_bonus, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.user_id, record.checkin_date.isoformat(),
                    record.points_earned, record.streak_bonus,
                    record.created_at.isoformat()
                )
            )
            await self.connection.commit()
            record_id = cursor.lastrowid
            logger.info(f"添加签到记录: ID={record_id}, 用户={record.user_id}, 日期={record.checkin_date}")
            return record_id
    
    # 签到处理逻辑
    async def process_checkin(
        bot: Bot, 
        user_id: int, 
        username: str, 
        chat_id: int, 
        message_id: int, 
        thread_id: Optional[int] = None
    ) -> None:
        """处理签到逻辑"""
        db = Database()
        try:
            await db.connect()
            
            # 获取用户信息，如果不存在则创建
            user = await db.get_user(user_id)
            if not user:
                user = User(user_id=user_id, username=username)
                await db.create_user(user)
            
            today = date.today()
            
            # 检查是否已经签到
            if user.last_checkin_date and user.last_checkin_date == today:
                # 已经签到过了
                reply_text = TEMPLATES["checkin_already"]
                await bot.send_message(
                    chat_id=chat_id,
                    text=reply_text,
                    reply_to_message_id=message_id,
                    message_thread_id=thread_id
                )
                return
            
            # 计算连续签到天数
            if user.last_checkin_date and (today - user.last_checkin_date).days == 1:
                # 连续签到
                user.streak_days += 1
            else:
                # 连续签到中断或首次签到
                user.streak_days = 1
            
            # 计算积分奖励
            base_points = DAILY_CHECKIN_POINTS
            bonus_points = 0
            
            # 检查是否达到连续签到奖励条件
            if user.streak_days == 7:
                bonus_points = WEEKLY_STREAK_POINTS
            elif user.streak_days == 30:
                bonus_points = MONTHLY_STREAK_POINTS
            
            total_points = base_points + bonus_points
            
            # 更新用户积分和签到信息
            user.points += total_points
            user.last_checkin_date = today
            user.total_checkins += 1
            user.monthly_checkins += 1
            
            # 保存用户信息
            await db.update_user(user)
            
            # 记录积分交易
            transaction = PointsTransaction(
                user_id=user_id,
                amount=base_points,
                transaction_type=PointsTransactionType.CHECKIN,
                description=f"每日签到奖励"
            )
            await db.add_points_transaction(transaction)
            
            # 如果有额外奖励，再记录一笔交易
            if bonus_points > 0:
                bonus_transaction = PointsTransaction(
                    user_id=user_id,
                    amount=bonus_points,
                    transaction_type=PointsTransactionType.STREAK_BONUS,
                    description=f"连续签到{user.streak_days}天奖励"
                )
                await db.add_points_transaction(bonus_transaction)
            
            # 记录签到记录
            checkin_record = CheckinRecord(
                user_id=user_id,
                checkin_date=today,
                points_earned=base_points,
                streak_bonus=bonus_points
            )
            await db.add_checkin_record(checkin_record)
            
            # 计算下一个奖励所需天数和奖励积分
            if user.streak_days < 7:
                days_to_next_reward = 7 - user.streak_days
                next_reward_points = WEEKLY_STREAK_POINTS
            elif user.streak_days < 30:
                days_to_next_reward = 30 - user.streak_days
                next_reward_points = MONTHLY_STREAK_POINTS
            else:
                days_to_next_reward = 0
                next_reward_points = 0
            
            # 格式化数字
            formatted_points = format_number(user.points)
            
            # 发送签到成功消息
            if user.streak_days == 30:
                # 月度签到奖励
                reply_text = TEMPLATES["checkin_monthly_bonus"].format(
                    username=username,
                    base_points=base_points,
                    bonus_points=bonus_points,
                    total_points=formatted_points,
                    streak_days=user.streak_days
                )
            elif bonus_points > 0:
                # 周签到奖励
                reply_text = TEMPLATES["checkin_streak_bonus"].format(
                    username=username,
                    base_points=base_points,
                    bonus_points=bonus_points,
                    streak_days=user.streak_days,
                    total_points=formatted_points,
                    days_to_next_reward=days_to_next_reward,
                    next_reward_points=next_reward_points
                )
            else:
                # 普通签到
                reply_text = TEMPLATES["checkin_success"].format(
                    username=username,
                    points=base_points,
                    streak_days=user.streak_days,
                    total_points=formatted_points,
                    days_to_next_reward=days_to_next_reward,
                    next_reward_points=next_reward_points
                )
            
            await bot.send_message(
                chat_id=chat_id,
                text=reply_text,
                reply_to_message_id=message_id,
                message_thread_id=thread_id
            )
            
            logger.info(f"用户 {username}({user_id}) 签到成功，获得 {total_points} 积分，连续签到 {user.streak_days} 天")
            
        except Exception as e:
            logger.error(f"签到处理出错: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ 签到失败，请稍后再试！",
                reply_to_message_id=message_id,
                message_thread_id=thread_id
            )
        finally:
            await db.disconnect()
    
    # 命令处理函数
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理/start命令"""
        user = update.effective_user
        await update.message.reply_text(
            f"👋 你好，{user.first_name}！\n"
            f"欢迎使用Coser社群Bot！\n\n"
            f"🔹 使用 /help 查看可用命令\n"
            f"🔹 每日签到可以获取积分\n"
            f"🔹 连续签到有额外奖励哦~"
        )
    
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理/help命令"""
        help_text = (
            "📋 可用命令列表：\n\n"
            "🔸 /start - 开始使用机器人\n"
            "🔸 /help - 获取帮助信息\n"
            "🔸 /checkin - 每日签到\n"
            "🔸 /points - 查询积分\n"
            "🔸 /gift - 赠送积分\n"
            "🔸 /bind_email - 绑定邮箱\n"
            "🔸 /verify - 验证邮箱\n\n"
            "💡 提示：直接发送「签到」也可以完成签到哦~"
        )
        await update.message.reply_text(help_text)
    
    async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理/checkin命令"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        message_id = update.effective_message.message_id
        thread_id = update.effective_message.message_thread_id
        
        logger.info(f"用户 {user.username or user.first_name}({user.id}) 发送了签到命令，聊天ID: {chat_id}, 话题ID: {thread_id}")
        
        await process_checkin(
            context.bot,
            user.id,
            user.username or f"user_{user.id}",
            chat_id,
            message_id,
            thread_id
        )
    
    async def checkin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理"签到"文本消息"""
        if update.message and update.message.text and update.message.text.strip() == "签到":
            user = update.effective_user
            chat_id = update.effective_chat.id
            message_id = update.effective_message.message_id
            thread_id = update.effective_message.message_thread_id
            
            logger.info(f"用户 {user.username or user.first_name}({user.id}) 发送了签到文本，聊天ID: {chat_id}, 话题ID: {thread_id}")
            
            await process_checkin(
                context.bot,
                user.id,
                user.username or f"user_{user.id}",
                chat_id,
                message_id,
                thread_id
            )
    
    # 初始化数据库
    async def initialize_database():
        """初始化数据库"""
        db = Database()
        try:
            await db.connect()
            await db.initialize()
        finally:
            await db.disconnect()
    
    # 主函数
    async def main():
        """主函数"""
        print("🚀 正在启动Coser社群Bot...")
        logger.info("Coser社群Bot启动中...")
        
        # 初始化数据库
        await initialize_database()
        
        # 创建应用
        application = Application.builder().token(BOT_TOKEN).build()
        
        # 注册基本命令处理器
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("checkin", checkin_command))
        
        # 注册文本消息处理器，支持普通群组和Topics群组
        application.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r"^签到$") & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
            checkin_text
        ))
        
        # 启动机器人
        logger.info("Coser社群Bot已启动")
        print("✅ Coser社群Bot已成功启动！")
        await application.run_polling()
    
    # 运行主函数
    if __name__ == "__main__":
        asyncio.run(main())

except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("可能的原因: 缺少依赖项，请确保已安装所有依赖")
    traceback.print_exc()
except Exception as e:
    print(f"❌ 启动失败: {e}")
    traceback.print_exc() 