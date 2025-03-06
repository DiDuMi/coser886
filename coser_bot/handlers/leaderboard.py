"""
@description: 排行榜功能处理模块
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from ..database.storage import Storage
from ..database.models import User
from ..config.constants import TEMPLATES

logger = logging.getLogger(__name__)

def format_number(number: int) -> str:
    """格式化数字，添加千位分隔符"""
    return f"{number:,}"

async def get_leaderboard_text(board_type: str, user_id: int = None) -> str:
    """
    获取排行榜文本
    
    Args:
        board_type: 排行榜类型 (points/streak/monthly)
        user_id: 查询用户的ID，用于显示用户排名
        
    Returns:
        str: 排行榜文本
    """
    try:
        storage = Storage()
        users = storage.get_all_users()
        logger.info(f"获取到 {len(users)} 个用户数据")
        
        if not users:
            return TEMPLATES["leaderboard_empty"].format(
                title="暂无排行数据",
                update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        
        if board_type == "points":
            # 积分排行
            users.sort(key=lambda x: x.points, reverse=True)
            title = "🏆 积分排行榜 TOP 10"
            value_key = "points"
            value_suffix = "积分"
        elif board_type == "streak":
            # 连续签到排行
            users.sort(key=lambda x: x.streak_days, reverse=True)
            title = "🔥 连续签到排行榜 TOP 10"
            value_key = "streak_days"
            value_suffix = "天"
        elif board_type == "refresh":
            # 刷新当前排行榜
            return await get_leaderboard_text("points", user_id)
        else:  # monthly
            # 本月签到排行
            users.sort(key=lambda x: x.monthly_checkins, reverse=True)
            title = "📅 本月签到排行榜 TOP 10"
            value_key = "monthly_checkins"
            value_suffix = "次"
        
        # 生成排行榜文本
        text = f"<b>{title}</b>\n\n"
        
        # 添加排行榜说明
        descriptions = {
            "points": "💡 通过签到、完成任务等方式获得积分",
            "streak": "💡 连续签到天数，中断后将重新计算",
            "monthly": f"💡 {datetime.now().strftime('%Y年%m月')}签到统计"
        }
        if board_type in descriptions:
            text += f"{descriptions[board_type]}\n\n"
        
        # 显示排行榜内容
        for i, user in enumerate(users[:10], 1):
            rank_emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            value = getattr(user, value_key)
            display_name = user.first_name if hasattr(user, 'first_name') and user.first_name else user.username
            # 为当前用户添加标记
            if user_id and user.user_id == user_id:
                display_name = f"👉 {display_name}"
            text += f"{rank_emoji} {display_name}: {format_number(value)} {value_suffix}\n"
        
        # 如果提供了user_id，显示用户的排名
        if user_id:
            user_rank = next((i for i, u in enumerate(users, 1) if u.user_id == user_id), None)
            if user_rank:
                user = next(u for u in users if u.user_id == user_id)
                value = getattr(user, value_key)
                display_name = user.first_name if hasattr(user, 'first_name') and user.first_name else user.username
                
                # 添加分隔线
                text += "\n" + "─" * 20 + "\n"
                
                # 显示用户排名信息
                rank_text = "你的排名"
                if user_rank > 10:
                    rank_text = f"你的排名 (前{format_number(len(users))}名中)"
                text += f"📊 {rank_text}：第 {format_number(user_rank)} 名\n"
                text += f"📈 当前{value_key == 'points' and '积分' or value_key == 'streak_days' and '连续签到天数' or '本月签到次数'}：{format_number(value)} {value_suffix}"
                
                # 添加进度信息
                if user_rank > 10:
                    next_rank = user_rank - 1
                    if next_rank <= len(users):
                        next_user = users[next_rank - 1]
                        next_value = getattr(next_user, value_key)
                        diff = next_value - value
                        if diff > 0:
                            text += f"\n🎯 距离上一名还差：{format_number(diff)} {value_suffix}"
        
        # 添加底部信息
        text += f"\n\n⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if board_type != "refresh":
            text += "\n💭 点击下方按钮切换排行榜类型"
        
        logger.info(f"生成{title}成功")
        return text
        
    except Exception as e:
        logger.error(f"生成排行榜文本时出错: {e}", exc_info=True)
        return "❌ 生成排行榜时出错，请稍后再试"

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    显示排行榜命令处理器
    """
    logger.info(f"收到排行榜命令，用户: {update.effective_user.username} (ID: {update.effective_user.id})")
    
    try:
        # 创建排行榜类型选择按钮
        keyboard = [
            [
                InlineKeyboardButton("💰 积分排行", callback_data="leaderboard_points"),
                InlineKeyboardButton("🔥 连续签到", callback_data="leaderboard_streak")
            ],
            [
                InlineKeyboardButton("📅 本月签到", callback_data="leaderboard_monthly"),
                InlineKeyboardButton("🔄 刷新数据", callback_data="leaderboard_refresh")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否为话题消息
        message = update.message
        is_topic = getattr(message, 'is_topic_message', False)
        thread_id = getattr(message, 'message_thread_id', None)
        
        # 发送加载消息
        if is_topic and thread_id:
            # 在话题群组中回复，使用相同的话题ID
            loading_message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                message_thread_id=thread_id,
                text="⏳ 正在加载排行榜数据...",
                parse_mode=ParseMode.HTML
            )
        else:
            # 普通消息回复
            loading_message = await update.message.reply_text(
                "⏳ 正在加载排行榜数据...",
                parse_mode=ParseMode.HTML
            )
        
        # 获取排行榜数据
        text = await get_leaderboard_text("points", update.effective_user.id)
        
        # 更新消息
        await loading_message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        logger.info("排行榜显示成功")
    except Exception as e:
        logger.error(f"显示排行榜时出错: {e}", exc_info=True)
        error_message = "❌ 显示排行榜时出错，请稍后再试"
        if isinstance(e, Exception):
            error_message += f"\n错误信息: {str(e)}"
        
        # 根据消息类型发送错误信息
        if is_topic and thread_id:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                message_thread_id=thread_id,
                text=error_message
            )
        else:
            await update.message.reply_text(error_message)

async def handle_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理排行榜按钮回调
    """
    query = update.callback_query
    logger.info(f"收到排行榜回调，用户: {query.from_user.username} (ID: {query.from_user.id}), 数据: {query.data}")
    
    try:
        # 显示加载状态
        await query.answer("⏳ 正在更新排行榜...")
        
        # 解析回调数据
        _, board_type = query.data.split("_")
        
        # 获取排行榜文本
        text = await get_leaderboard_text(board_type, query.from_user.id)
        
        # 更新消息
        keyboard = [
            [
                InlineKeyboardButton("💰 积分排行", callback_data="leaderboard_points"),
                InlineKeyboardButton("🔥 连续签到", callback_data="leaderboard_streak")
            ],
            [
                InlineKeyboardButton("📅 本月签到", callback_data="leaderboard_monthly"),
                InlineKeyboardButton("🔄 刷新数据", callback_data="leaderboard_refresh")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"排行榜更新成功，类型: {board_type}")
    except Exception as e:
        logger.error(f"处理排行榜回调时出错: {e}", exc_info=True)
        await query.answer("❌ 更新排行榜时出错，请稍后再试")

def get_leaderboard_handlers():
    """获取排行榜相关的处理器列表"""
    handlers = [
        CommandHandler("leaderboard", show_leaderboard),
        CommandHandler("rank", show_leaderboard),  # 添加一个别名
        CallbackQueryHandler(handle_leaderboard_callback, pattern="^leaderboard_")
    ]
    return handlers 