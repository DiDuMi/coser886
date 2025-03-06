"""
@description: 签到功能处理模块
"""
import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional, Tuple, Dict, Any, List, Union

from telegram import Update, User as TelegramUser, Bot
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, Application, CallbackQueryHandler
from telegram.constants import ParseMode

from ..config.settings import (
    DAILY_CHECKIN_POINTS, WEEKLY_STREAK_POINTS, MONTHLY_STREAK_POINTS,
    CHECKIN_COOLDOWN_HOURS, MAKEUP_CHECKIN_ENABLED, MAKEUP_CHECKIN_COST,
    MAKEUP_CHECKIN_MAX_DAYS
)
from ..config.constants import TEMPLATES
from ..database.models import User, CheckinRecord, PointsTransaction, PointsTransactionType
from ..database.storage import Storage

logger = logging.getLogger(__name__)

def format_number(number: int) -> str:
    """
    @description: 格式化数字，添加千位分隔符
    @param {int} number: 要格式化的数字
    @return {str}: 格式化后的字符串
    """
    return f"{number:,}"

async def checkin_user(user_id: int, username: str) -> Tuple[bool, str]:
    """
    处理用户签到逻辑
    
    Args:
        user_id: 用户ID
        username: 用户名
        
    Returns:
        Tuple[bool, str]: (是否成功, 签到结果消息)
    """
    try:
        # 获取存储对象
        storage = Storage()
        
        # 获取或创建用户
        user = storage.get_user(user_id)
        if not user:
            logger.warning(f"用户 {username} (ID: {user_id}) 不存在")
            return False, "❌ 用户信息不存在，请先使用 /start 命令注册"
        
        # 获取今天的日期
        today = date.today()
        
        # 检查用户是否已经今天签到过
        latest_record = storage.get_user_last_checkin_record(user_id)
        if latest_record and latest_record.checkin_date == today:
            # 已经签到过了
            hours, remainder = divmod((datetime.now() - latest_record.created_at).seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_ago = f"{hours}小时{minutes}分钟前"
            
            logger.info(f"用户 {username} (ID: {user_id}) 今天已经签到过了 ({time_ago})")
            return False, TEMPLATES["checkin_already"].format(
                time=time_ago,
                points=user.points,
                streak_days=user.streak_days
            )
        
        # 计算签到信息
        is_streak = False
        is_first_checkin = True
        streak_bonus = 0
        
        if latest_record:
            is_first_checkin = False
            yesterday = today - timedelta(days=1)
            
            # 检查是否是连续签到
            if latest_record.checkin_date.date() == yesterday:
                is_streak = True
                # 更新连续签到天数
                user.streak_days += 1
                
                # 检查是否达到连续签到奖励条件
                if user.streak_days % 30 == 0:  # 每30天额外奖励
                    streak_bonus += MONTHLY_STREAK_POINTS
                elif user.streak_days % 7 == 0:  # 每7天额外奖励
                    streak_bonus += WEEKLY_STREAK_POINTS
            else:
                # 连续签到中断
                user.streak_days = 1
        else:
            # 首次签到
            user.streak_days = 1
        
        # 更新最长连续签到记录
        if user.streak_days > user.max_streak_days:
            user.max_streak_days = user.streak_days
        
        # 基础签到积分
        points = DAILY_CHECKIN_POINTS
        
        # 更新用户数据
        user.points += points + streak_bonus
        user.total_checkins += 1
        user.monthly_checkins += 1
        
        # 如果是新的一个月，重置月签到次数
        current_month = today.month
        if latest_record and latest_record.checkin_date.date().month != current_month:
            user.monthly_checkins = 1
        
        # 保存用户数据
        storage.save_user(user)
        
        # 创建签到记录
        record = CheckinRecord(
            record_id=len(storage.checkin_records) + 1,
            user_id=user_id,
            checkin_date=datetime.now(),
            points=points,
            streak_days=user.streak_days,
            streak_bonus=streak_bonus
        )
        storage.add_checkin_record(record)
        
        # 创建积分交易记录
        transaction = PointsTransaction(
            transaction_id=len(storage.transactions) + 1,
            user_id=user_id,
            amount=points + streak_bonus,
            type=PointsTransactionType.CHECKIN,
            description=f"每日签到 +{points}" + (f" (连续{user.streak_days}天额外奖励 +{streak_bonus})" if streak_bonus > 0 else ""),
            created_at=datetime.now()
        )
        storage.add_transaction(transaction)
        
        # 保存数据
        storage.save_checkin_records()
        storage.save_transactions()
        
        # 构建签到成功消息
        if is_first_checkin:
            logger.info(f"用户 {username} (ID: {user_id}) 首次签到成功，获得 {points} 积分")
            return True, TEMPLATES["checkin_first_success"].format(
                points=points,
                total_points=user.points
            )
        elif is_streak:
            if streak_bonus > 0:
                logger.info(f"用户 {username} (ID: {user_id}) 连续{user.streak_days}天签到，获得额外 {streak_bonus} 积分")
                return True, TEMPLATES["checkin_streak_bonus"].format(
                    days=user.streak_days,
                    points=points,
                    bonus=streak_bonus,
                    total=points + streak_bonus,
                    total_points=user.points
                )
            else:
                logger.info(f"用户 {username} (ID: {user_id}) 连续{user.streak_days}天签到")
                return True, TEMPLATES["checkin_streak_success"].format(
                    days=user.streak_days,
                    points=points,
                    total_points=user.points
                )
        else:
            logger.info(f"用户 {username} (ID: {user_id}) 签到成功，重新开始连续签到")
            return True, TEMPLATES["checkin_restart_success"].format(
                points=points,
                total_points=user.points
            )
            
    except Exception as e:
        logger.error(f"处理用户 {username} (ID: {user_id}) 签到时出错: {e}", exc_info=True)
        return False, "❌ 签到处理过程中出错，请稍后再试"

async def process_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    @description: 处理用户签到
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    @return {str}: 签到结果消息
    """
    # 获取用户信息
    telegram_user = update.effective_user
    if not telegram_user:
        logger.warning("无法获取用户信息")
        return "❌ 无法获取用户信息，请稍后再试"
    
    # 获取存储对象
    storage = Storage()
    
    # 获取或创建用户
    user = storage.get_user(telegram_user.id)
    if not user:
        user = User(
            user_id=telegram_user.id,
            username=telegram_user.username or telegram_user.first_name,
            join_date=datetime.now(),
            points=0
        )
        storage.save_user(user)
        logger.info(f"创建新用户: {user.username} (ID: {user.user_id})")
    
    # 检查今天是否已经签到
    today = date.today()
    if user.last_checkin_date and user.last_checkin_date == today:
        # 已经签到过了
        logger.info(f"用户 {user.username} (ID: {user.user_id}) 今天已经签到过了")
        return TEMPLATES["checkin_already"].format(
            points=format_number(user.points),
            streak_days=user.streak_days
        )
    
    # 计算连续签到天数
    is_streak_broken = False
    if user.last_checkin_date:
        yesterday = today - timedelta(days=1)
        if user.last_checkin_date < yesterday:
            # 连续签到中断
            is_streak_broken = True
            user.streak_days = 1
        else:
            # 连续签到
            user.streak_days += 1
    else:
        # 首次签到
        user.streak_days = 1
    
    # 更新最长连续签到记录
    if user.streak_days > user.max_streak_days:
        user.max_streak_days = user.streak_days
        user.longest_streak_start = today - timedelta(days=user.streak_days - 1)
        user.longest_streak_end = today
    
    # 更新用户签到信息
    user.last_checkin_date = today
    user.total_checkins += 1
    user.monthly_checkins += 1
    
    # 更新最近签到统计
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    user_records = storage.get_user_checkin_records(user.user_id)
    user.last_week_checkins = sum(1 for r in user_records if r.checkin_date > week_ago)
    user.last_month_checkins = sum(1 for r in user_records if r.checkin_date > month_ago)
    
    # 计算积分奖励
    base_points = DAILY_CHECKIN_POINTS
    streak_bonus = 0
    monthly_bonus = 0
    
    # 计算连续签到奖励
    if user.streak_days % 30 == 0:
        # 每月奖励
        monthly_bonus = MONTHLY_STREAK_POINTS
        total_points = base_points + monthly_bonus
        user.points += total_points
        user.total_points_earned += total_points
        
        # 创建签到记录
        checkin_record = CheckinRecord(
            user_id=user.user_id,
            checkin_date=today,
            points_earned=base_points,
            streak_bonus=monthly_bonus
        )
        storage.add_checkin_record(checkin_record)
        
        # 创建积分交易记录
        transaction = PointsTransaction(
            user_id=user.user_id,
            amount=total_points,
            transaction_type=PointsTransactionType.CHECKIN,
            description=f"第{user.streak_days}天签到 (月度奖励)"
        )
        storage.save_transaction(transaction)
        
        # 保存用户信息
        storage.save_user(user)
        
        logger.info(f"用户 {user.username} (ID: {user.user_id}) 完成第{user.streak_days}天签到，获得{base_points}基础积分和{monthly_bonus}月度奖励")
        
        return TEMPLATES["checkin_monthly_bonus"].format(
            username=telegram_user.username or telegram_user.first_name,
            date=today.strftime("%Y-%m-%d"),
            streak_days=user.streak_days,
            base_points=format_number(base_points),
            monthly_bonus=format_number(monthly_bonus),
            total_points=format_number(user.points)
        )
        
    elif user.streak_days % 7 == 0:
        # 每周奖励
        streak_bonus = WEEKLY_STREAK_POINTS
        total_points = base_points + streak_bonus
        user.points += total_points
        user.total_points_earned += total_points
        
        # 创建签到记录
        checkin_record = CheckinRecord(
            user_id=user.user_id,
            checkin_date=today,
            points_earned=base_points,
            streak_bonus=streak_bonus
        )
        storage.add_checkin_record(checkin_record)
        
        # 创建积分交易记录
        transaction = PointsTransaction(
            user_id=user.user_id,
            amount=total_points,
            transaction_type=PointsTransactionType.CHECKIN,
            description=f"第{user.streak_days}天签到 (周奖励)"
        )
        storage.save_transaction(transaction)
        
        # 保存用户信息
        storage.save_user(user)
        
        logger.info(f"用户 {user.username} (ID: {user.user_id}) 完成第{user.streak_days}天签到，获得{base_points}基础积分和{streak_bonus}周奖励")
        
        return TEMPLATES["checkin_streak_bonus"].format(
            username=telegram_user.username or telegram_user.first_name,
            date=today.strftime("%Y-%m-%d"),
            streak_days=user.streak_days,
            base_points=format_number(base_points),
            bonus_points=format_number(streak_bonus),
            total_points=format_number(user.points)
        )
        
    else:
        # 普通签到
        user.points += base_points
        user.total_points_earned += base_points
        
        # 创建签到记录
        checkin_record = CheckinRecord(
            user_id=user.user_id,
            checkin_date=today,
            points_earned=base_points
        )
        storage.add_checkin_record(checkin_record)
        
        # 创建积分交易记录
        transaction = PointsTransaction(
            user_id=user.user_id,
            amount=base_points,
            transaction_type=PointsTransactionType.CHECKIN,
            description=f"第{user.streak_days}天签到"
        )
        storage.save_transaction(transaction)
        
        # 保存用户信息
        storage.save_user(user)
        
        logger.info(f"用户 {user.username} (ID: {user.user_id}) 完成第{user.streak_days}天签到，获得{base_points}积分")
    
    if is_streak_broken:
        # 连续签到中断
        return TEMPLATES["checkin_success"].format(
            username=telegram_user.username or telegram_user.first_name,
            date=today.strftime("%Y-%m-%d"),
            streak_days=user.streak_days,
            points=format_number(base_points),
            total_points=format_number(user.points)
        )
    else:
        # 连续签到
        return TEMPLATES["checkin_success"].format(
            username=telegram_user.username or telegram_user.first_name,
            date=today.strftime("%Y-%m-%d"),
            streak_days=user.streak_days,
            points=format_number(base_points),
            total_points=format_number(user.points)
        )

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理签到命令
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    try:
        reply_text = await process_checkin(update, context)
        await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"签到命令处理出错: {e}", exc_info=True)
        await update.message.reply_text("❌ 签到失败，请稍后再试")

async def checkin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理包含"签到"文本的消息
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip().lower()
    if "签到" in text:
        try:
            reply_text = await process_checkin(update, context)
            await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"签到文本处理出错: {e}", exc_info=True)
            await update.message.reply_text("❌ 签到失败，请稍后再试")

async def process_checkin_callback(
    bot: Bot, 
    user_id: int, 
    username: str, 
    chat_id: int, 
    message_id: int, 
    thread_id: Optional[int] = None
) -> None:
    """
    @description: 处理签到逻辑
    @param {Bot} bot: Telegram Bot对象
    @param {int} user_id: 用户ID
    @param {str} username: 用户名
    @param {int} chat_id: 聊天ID
    @param {int} message_id: 消息ID
    @param {Optional[int]} thread_id: 话题ID
    @return {None}
    """
    storage = Storage()
    try:
        # 获取用户信息，如果不存在则创建
        user = storage.get_user(user_id)
        if not user:
            user = User(user_id=user_id, username=username)
            storage.save_user(user)
        
        today = date.today()
        
        # 检查是否已经签到
        if user.last_checkin_date and user.last_checkin_date == today:
            # 已经签到过了
            logger.info(f"用户 {user.username} (ID: {user.user_id}) 今天已经签到过了")
            reply_text = TEMPLATES["checkin_already"].format(
                points=format_number(user.points),
                streak_days=user.streak_days
            )
            await bot.send_message(
                chat_id=chat_id,
                text=reply_text,
                reply_to_message_id=message_id,
                message_thread_id=thread_id,
                parse_mode=ParseMode.HTML
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
        storage.save_user(user)
        
        # 记录积分交易
        transaction = PointsTransaction(
            user_id=user_id,
            amount=base_points,
            transaction_type=PointsTransactionType.CHECKIN,
            description=f"每日签到奖励"
        )
        storage.add_transaction(transaction)
        
        # 如果有额外奖励，再记录一笔交易
        if bonus_points > 0:
            bonus_transaction = PointsTransaction(
                user_id=user_id,
                amount=bonus_points,
                transaction_type=PointsTransactionType.STREAK_BONUS,
                description=f"连续签到{user.streak_days}天奖励"
            )
            storage.add_transaction(bonus_transaction)
        
        # 记录签到记录
        checkin_record = CheckinRecord(
            user_id=user_id,
            checkin_date=today,
            points_earned=base_points,
            streak_bonus=bonus_points
        )
        storage.add_checkin_record(checkin_record)
        
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
                monthly_bonus=bonus_points,
                total_points=formatted_points,
                streak_days=user.streak_days,
                date=today.strftime("%Y-%m-%d")
            )
        elif bonus_points > 0:
            # 周签到奖励
            reply_text = TEMPLATES["checkin_streak_bonus"].format(
                username=username,
                base_points=base_points,
                bonus_points=bonus_points,
                streak_days=user.streak_days,
                total_points=formatted_points,
                date=today.strftime("%Y-%m-%d")
            )
        else:
            # 普通签到
            reply_text = TEMPLATES["checkin_success"].format(
                username=username,
                points=base_points,
                streak_days=user.streak_days,
                total_points=formatted_points,
                date=today.strftime("%Y-%m-%d")
            )
        
        await bot.send_message(
            chat_id=chat_id,
            text=reply_text,
            reply_to_message_id=message_id,
            message_thread_id=thread_id,
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"用户 {username}({user_id}) 签到成功，获得 {total_points} 积分，连续签到 {user.streak_days} 天")
        
    except Exception as e:
        logger.error(f"签到处理出错: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ 签到失败，请稍后再试！",
            reply_to_message_id=message_id,
            message_thread_id=thread_id,
            parse_mode=ParseMode.HTML
        )

async def handle_checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理/checkin命令
    @param {Update} update: 更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    @return {None}
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    message_id = update.effective_message.message_id
    thread_id = update.effective_message.message_thread_id
    
    logger.info(f"用户 {user.username or user.first_name}({user.id}) 发送了签到命令，聊天ID: {chat_id}, 话题ID: {thread_id}")
    
    await process_checkin_callback(
        context.bot,
        user.id,
        user.username or f"user_{user.id}",
        chat_id,
        message_id,
        thread_id
    )

async def handle_checkin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理"签到"文本消息
    @param {Update} update: 更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    @return {None}
    """
    if update.message and update.message.text and update.message.text.strip() == "签到":
        user = update.effective_user
        chat_id = update.effective_chat.id
        message_id = update.effective_message.message_id
        thread_id = update.effective_message.message_thread_id
        
        logger.info(f"用户 {user.username or user.first_name}({user.id}) 发送了签到文本，聊天ID: {chat_id}, 话题ID: {thread_id}")
        
        await process_checkin_callback(
            context.bot,
            user.id,
            user.username or f"user_{user.id}",
            chat_id,
            message_id,
            thread_id
        )

def register_handlers(application):
    """
    @description: 注册签到相关的处理器
    @param application: 应用对象
    @return {None}
    """
    # 注册命令处理器
    application.add_handler(CommandHandler("checkin", handle_checkin_command))
    
    # 注册文本消息处理器，支持普通群组和Topics群组
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^签到$") & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
        handle_checkin_text
    )) 

def get_checkin_handlers():
    """
    @description: 获取签到相关的处理器列表
    @return {List}: 处理器列表
    """
    handlers = [
        CommandHandler("checkin", handle_checkin_command),
        
        # 处理文本消息中的签到关键词
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^签到$'), 
            handle_checkin_text
        )
    ]
    
    return handlers 