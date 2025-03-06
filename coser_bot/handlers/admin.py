"""
@description: 管理员命令处理模块
"""
import logging
import csv
import os
from datetime import datetime
from typing import List, Dict
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    BaseHandler
)
from telegram.constants import ParseMode

from coser_bot.config.settings import ADMIN_IDS, DATA_DIR
from coser_bot.config.constants import TEMPLATES
from coser_bot.database.storage import Storage
from coser_bot.database.models import Group, PointsTransaction, PointsTransactionType, User

logger = logging.getLogger(__name__)

# 会话状态
WAITING_FOR_GROUP_NAME = 1
WAITING_FOR_POINTS = 2
WAITING_FOR_DAYS = 3
WAITING_FOR_CSV_FILE = 1

# 存储等待导入积分的用户数据
# 格式: {user_id: {"points": points, "source": source}}
pending_import_points = {}

async def admin_group_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理添加权益群组的命令"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔️ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 检查命令格式
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ 请提供群组ID\n用法：<code>/admin_group_add &lt;群组ID&gt;</code>",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    try:
        group_id = int(context.args[0])
        context.user_data['temp_group_id'] = group_id
        
        await update.message.reply_text(
            "请输入群组名称：",
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_GROUP_NAME
        
    except ValueError:
        await update.message.reply_text(
            "❌ 群组ID必须是数字",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

async def group_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理群组名称输入"""
    group_name = update.message.text.strip()
    context.user_data['temp_group_name'] = group_name
    
    await update.message.reply_text(
        "请输入加入群组所需的积分数量（输入0表示不需要积分）：",
        parse_mode=ParseMode.HTML
    )
    return WAITING_FOR_POINTS

async def points_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理积分要求输入"""
    try:
        points = int(update.message.text.strip())
        if points < 0:
            await update.message.reply_text(
                "❌ 积分数量不能为负数",
                parse_mode=ParseMode.HTML
            )
            return WAITING_FOR_POINTS
            
        context.user_data['temp_points'] = points
        
        await update.message.reply_text(
            "请输入访问有效期（天数，输入0表示永久有效）：",
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_DAYS
        
    except ValueError:
        await update.message.reply_text(
            "❌ 请输入有效的数字",
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_POINTS

async def days_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理有效期输入并保存群组信息"""
    try:
        days = int(update.message.text.strip())
        if days < 0:
            await update.message.reply_text(
                "❌ 天数不能为负数",
                parse_mode=ParseMode.HTML
            )
            return WAITING_FOR_DAYS
        
        # 创建群组对象
        group = Group(
            group_id=context.user_data['temp_group_id'],
            group_name=context.user_data['temp_group_name'],
            chat_id=context.user_data['temp_group_id'],  # 使用 group_id 作为 chat_id
            is_paid=context.user_data['temp_points'] > 0,
            required_points=context.user_data['temp_points'],
            access_days=days
        )
        
        # 保存群组信息
        storage = Storage()
        if storage.save_group(group):
            await update.message.reply_text(
                f"✅ 群组添加成功！\n\n"
                f"群组ID：{group.group_id}\n"
                f"名称：{group.group_name}\n"
                f"类型：{'付费' if group.is_paid else '免费'}\n"
                f"所需积分：{group.required_points}\n"
                f"有效期：{'永久' if group.access_days == 0 else f'{group.access_days}天'}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ 保存群组信息失败",
                parse_mode=ParseMode.HTML
            )
        
        # 清理临时数据
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ 请输入有效的数字",
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_DAYS

async def admin_group_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理删除权益群组的命令"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔️ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ 请提供群组ID\n用法：/admin_group_remove <群组ID>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        group_id = int(context.args[0])
        storage = Storage()
        group = storage.get_group(group_id)
        
        if not group:
            await update.message.reply_text(
                "❌ 找不到指定的群组",
                parse_mode=ParseMode.HTML
            )
            return
        
        # 删除群组
        if group_id in storage.groups:
            del storage.groups[group_id]
            storage._save_data()
            
            await update.message.reply_text(
                f"✅ 已成功删除群组：{group.group_name}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ 删除群组失败",
                parse_mode=ParseMode.HTML
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ 群组ID必须是数字",
            parse_mode=ParseMode.HTML
        )

async def admin_group_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """列出所有付费群组"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔️ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return
    
    storage = Storage()
    groups = storage.groups
    
    if not groups:
        await update.message.reply_text(
            "📋 <b>群组列表</b>\n\n"
            "目前没有添加任何群组。\n"
            "使用 /admin_group_add 命令添加群组。",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 按ID排序
    sorted_groups = sorted(groups.values(), key=lambda x: x.group_id)
    
    message = "📋 <b>群组列表</b>\n\n"
    for i, group in enumerate(sorted_groups, 1):
        message += f"{i}. <b>{group.group_name}</b>\n"
        message += f"   ID: {group.group_id}\n"
        message += f"   所需积分: {group.required_points}\n"
        message += f"   激活天数: {group.access_days}\n"
        message += "\n"
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML
    )

async def admin_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """调整用户积分"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔️ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 检查命令格式
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ 请提供用户ID和积分数量\n用法：<code>/admin_points &lt;用户ID/用户名&gt; &lt;积分数量&gt;</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 解析参数
    target_user_id_or_username = context.args[0]
    try:
        points_change = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ 积分数量必须是整数",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 获取存储对象
    storage = Storage()
    
    # 查找目标用户
    target_user = None
    
    # 检查是否为用户ID
    if target_user_id_or_username.isdigit():
        target_user_id = int(target_user_id_or_username)
        target_user = storage.get_user(target_user_id)
    else:
        # 检查是否为@用户名
        username = target_user_id_or_username.lstrip('@')
        # 在所有用户中查找匹配的用户名
        for user in storage.users.values():
            if user.username and user.username.lower() == username.lower():
                target_user = user
                break
    
    if not target_user:
        await update.message.reply_text(
            f"❌ 找不到用户: {target_user_id_or_username}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 更新用户积分
    old_points = target_user.points
    target_user.points += points_change
    
    # 确保积分不为负数
    if target_user.points < 0:
        target_user.points = 0
    
    # 保存用户数据
    storage.save_user(target_user)
    
    # 记录积分交易
    transaction = PointsTransaction(
        user_id=target_user.user_id,
        amount=points_change,
        transaction_type=PointsTransactionType.ADMIN_ADJUSTMENT,
        description=f"管理员调整 (by {update.effective_user.username or update.effective_user.id})",
        created_at=datetime.now()
    )
    storage.save_transaction(transaction)
    
    # 发送确认消息
    sign = "+" if points_change > 0 else ""
    await update.message.reply_text(
        f"✅ 已调整用户 {target_user.username or target_user.user_id} 的积分\n\n"
        f"调整: {sign}{points_change} 积分\n"
        f"原积分: {old_points} 积分\n"
        f"现积分: {target_user.points} 积分",
        parse_mode=ParseMode.HTML
    )
    
    logger.info(f"管理员 {update.effective_user.username or update.effective_user.id} 调整了用户 {target_user.username or target_user.user_id} 的积分: {sign}{points_change}")

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """列出所有用户"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔️ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return
    
    storage = Storage()
    users = storage.users
    
    if not users:
        await update.message.reply_text(
            "📋 <b>用户列表</b>\n\n"
            "目前没有任何用户。",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 按积分排序
    sorted_users = sorted(users.values(), key=lambda x: x.points, reverse=True)
    
    # 分页显示，每页10个用户
    page = 1
    if len(context.args) > 0:
        try:
            page = int(context.args[0])
            if page < 1:
                page = 1
        except ValueError:
            page = 1
    
    per_page = 10
    total_pages = (len(sorted_users) + per_page - 1) // per_page
    
    if page > total_pages:
        page = total_pages
    
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, len(sorted_users))
    
    # 计算统计信息
    total_points = sum(user.points for user in sorted_users)
    avg_points = total_points / len(sorted_users) if sorted_users else 0
    verified_users = sum(1 for user in sorted_users if user.email_verified)
    
    message = f"📋 <b>用户列表</b> (共 {len(sorted_users)} 名成员)\n"
    message += f"📊 第 {page}/{total_pages} 页\n"
    message += f"💰 积分总量: {total_points} | 平均: {avg_points:.1f}\n"
    message += f"📧 已验证邮箱: {verified_users}/{len(sorted_users)} ({verified_users/len(sorted_users)*100:.1f}%)\n\n"
    
    for i, user in enumerate(sorted_users[start_idx:end_idx], start_idx + 1):
        username = user.username or "无用户名"
        message += f"{i}. <b>{username}</b>\n"
        message += f"   ID: {user.user_id}\n"
        message += f"   积分: {user.points}\n"
        message += f"   加入时间: {user.join_date.strftime('%Y-%m-%d')}\n"
        
        # 添加邮箱验证状态
        email_status = "✅ 已验证" if user.email_verified else "❌ 未验证"
        message += f"   邮箱: {user.email or '未绑定'} {email_status if user.email else ''}\n"
        
        # 添加最后签到时间
        last_checkin = "从未签到" if not user.last_checkin_date else user.last_checkin_date.strftime('%Y-%m-%d')
        message += f"   最后签到: {last_checkin}\n"
        
        message += "\n"
    
    # 创建键盘按钮
    keyboard = []
    
    # 为每个用户添加查看详情按钮
    for user in sorted_users[start_idx:end_idx]:
        username = user.username or "无用户名"
        keyboard.append([InlineKeyboardButton(f"👤 查看 {username} 详情", callback_data=f"admin_info_{user.user_id}")])
    
    # 添加分页导航按钮
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"admin_list_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"admin_list_{page+1}"))
        keyboard.append(nav_buttons)
    
    # 添加刷新按钮
    keyboard.append([InlineKeyboardButton("🔄 刷新", callback_data=f"admin_list_{page}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def admin_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理用户列表分页回调"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.answer("⛔️ 只有管理员可以使用此功能")
        return
    
    # 提取页码
    match = re.match(r"admin_list_(\d+)", query.data)
    if not match:
        await query.answer("无效的回调数据")
        return
    
    page = int(match.group(1))
    
    # 获取用户列表
    storage = Storage()
    users = storage.users
    
    # 按积分排序
    sorted_users = sorted(users.values(), key=lambda x: x.points, reverse=True)
    
    # 分页显示
    per_page = 10
    total_pages = (len(sorted_users) + per_page - 1) // per_page
    
    if page > total_pages:
        page = total_pages
    if page < 1:
        page = 1
    
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, len(sorted_users))
    
    # 计算统计信息
    total_points = sum(user.points for user in sorted_users)
    avg_points = total_points / len(sorted_users) if sorted_users else 0
    verified_users = sum(1 for user in sorted_users if user.email_verified)
    
    message = f"📋 <b>用户列表</b> (共 {len(sorted_users)} 名成员)\n"
    message += f"📊 第 {page}/{total_pages} 页\n"
    message += f"💰 积分总量: {total_points} | 平均: {avg_points:.1f}\n"
    message += f"📧 已验证邮箱: {verified_users}/{len(sorted_users)} ({verified_users/len(sorted_users)*100:.1f}%)\n\n"
    
    for i, user in enumerate(sorted_users[start_idx:end_idx], start_idx + 1):
        username = user.username or "无用户名"
        message += f"{i}. <b>{username}</b>\n"
        message += f"   ID: {user.user_id}\n"
        message += f"   积分: {user.points}\n"
        message += f"   加入时间: {user.join_date.strftime('%Y-%m-%d')}\n"
        
        # 添加邮箱验证状态
        email_status = "✅ 已验证" if user.email_verified else "❌ 未验证"
        message += f"   邮箱: {user.email or '未绑定'} {email_status if user.email else ''}\n"
        
        # 添加最后签到时间
        last_checkin = "从未签到" if not user.last_checkin_date else user.last_checkin_date.strftime('%Y-%m-%d')
        message += f"   最后签到: {last_checkin}\n"
        
        message += "\n"
    
    # 创建键盘按钮
    keyboard = []
    
    # 为每个用户添加查看详情按钮
    for user in sorted_users[start_idx:end_idx]:
        username = user.username or "无用户名"
        keyboard.append([InlineKeyboardButton(f"👤 查看 {username} 详情", callback_data=f"admin_info_{user.user_id}")])
    
    # 添加分页导航按钮
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"admin_list_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"admin_list_{page+1}"))
        keyboard.append(nav_buttons)
    
    # 添加刷新按钮
    keyboard.append([InlineKeyboardButton("🔄 刷新", callback_data=f"admin_list_{page}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await query.answer()
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def admin_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看用户详细信息"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔️ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 检查命令格式
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ 请提供用户ID\n用法：<code>/admin_info &lt;用户ID/用户名&gt;</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 解析参数
    target_user_id_or_username = context.args[0]
    
    # 获取存储对象
    storage = Storage()
    
    # 查找目标用户
    target_user = None
    
    # 检查是否为用户ID
    if target_user_id_or_username.isdigit():
        target_user_id = int(target_user_id_or_username)
        target_user = storage.get_user(target_user_id)
    else:
        # 检查是否为@用户名
        username = target_user_id_or_username.lstrip('@')
        # 在所有用户中查找匹配的用户名
        for user in storage.users.values():
            if user.username and user.username.lower() == username.lower():
                target_user = user
                break
    
    if not target_user:
        await update.message.reply_text(
            f"❌ 找不到用户: {target_user_id_or_username}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 获取用户的签到记录
    checkins = storage.get_user_checkins(target_user.user_id)
    total_checkins = len(checkins)
    
    # 获取用户的交易记录
    transactions = storage.get_user_transactions(target_user.user_id)
    
    # 计算收到和发出的礼物
    received_gifts = 0
    sent_gifts = 0
    for tx in transactions:
        if tx.transaction_type == PointsTransactionType.GIFT_RECEIVED:
            received_gifts += 1
        elif tx.transaction_type == PointsTransactionType.GIFT_SENT:
            sent_gifts += 1
    
    # 获取用户的邮箱验证状态
    email_verifications = storage.get_user_email_verifications(target_user.user_id)
    email_status = "未验证"
    if email_verifications:
        for verification in email_verifications:
            if verification.is_verified:
                email_status = f"已验证 ({verification.email})"
                break
    
    # 获取用户的群组权限
    group_permissions = storage.get_user_group_permissions(target_user.user_id)
    groups_info = []
    for perm in group_permissions:
        group = storage.get_group(perm.group_id)
        if group:
            expiry_info = "永久" if perm.expiry_date is None else f"到期: {perm.expiry_date.strftime('%Y-%m-%d')}"
            groups_info.append(f"{group.group_name} ({expiry_info})")
    
    groups_text = "\n".join([f"• {g}" for g in groups_info]) if groups_info else "无"
    
    # 构建用户信息消息
    message = f"""
👤 <b>用户详细信息</b>

📋 用户名：@{target_user.username or '无'}
🆔 用户ID：{target_user.user_id}
📅 加入时间：{target_user.join_date.strftime('%Y-%m-%d %H:%M:%S')}
💰 当前积分：{target_user.points}
❄️ 冻结积分：{target_user.frozen_points}
📊 连续签到：{target_user.streak_days}天
✉️ 邮箱状态：{email_status}

<b>累计数据：</b>
📝 总签到次数：{total_checkins}
🎁 收到礼物：{received_gifts}
💝 发出礼物：{sent_gifts}

<b>群组权限：</b>
{groups_text}
"""
    
    # 添加最近交易记录
    recent_transactions = storage.get_user_transactions(target_user.user_id, limit=5)
    if recent_transactions:
        message += "\n<b>最近交易记录：</b>\n"
        for tx in recent_transactions:
            tx_time = tx.created_at.strftime("%Y-%m-%d %H:%M")
            amount_str = f"+{tx.amount}" if tx.amount > 0 else f"{tx.amount}"
            message += f"• {tx_time} {amount_str} 积分 - {tx.description}\n"
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML
    )

async def admin_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理查看用户详情回调"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # 检查是否是管理员
    if user_id not in ADMIN_IDS:
        await query.answer("您没有管理员权限")
        return
    
    # 从回调数据中提取用户ID
    match = re.match(r"admin_info_(\d+)", query.data)
    if not match:
        await query.answer("无效的回调数据")
        return
    
    target_user_id = int(match.group(1))
    
    # 获取用户信息
    storage = Storage()
    user = storage.get_user(target_user_id)
    
    if not user:
        await query.answer("找不到该用户")
        return
    
    # 获取用户的积分交易记录
    transactions = storage.get_user_transactions(target_user_id, limit=10)
    
    # 构建详细信息消息
    username = user.username or "无用户名"
    message = f"👤 <b>用户详情</b>\n\n"
    message += f"用户名: {username}\n"
    message += f"用户ID: {user.user_id}\n"
    message += f"积分: {user.points}\n"
    message += f"加入时间: {user.join_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    # 邮箱信息
    email_status = "✅ 已验证" if user.email_verified else "❌ 未验证"
    message += f"邮箱: {user.email or '未绑定'} {email_status if user.email else ''}\n"
    
    # 签到信息
    last_checkin = "从未签到" if not user.last_checkin_date else user.last_checkin_date.strftime('%Y-%m-%d %H:%M:%S')
    message += f"最后签到: {last_checkin}\n"
    message += f"连续签到: {user.streak_days} 天\n"
    message += f"总签到次数: {user.total_checkins} 次\n\n"
    
    # 最近的积分交易记录
    if transactions:
        message += "<b>最近积分记录</b>\n"
        for tx in transactions:
            date_str = tx.created_at.strftime('%Y-%m-%d %H:%M')
            amount = f"+{tx.amount}" if tx.amount > 0 else f"{tx.amount}"
            message += f"{date_str}: {tx.transaction_type} {amount} 积分\n"
    else:
        message += "<b>暂无积分记录</b>\n"
    
    # 创建返回按钮
    keyboard = [
        [InlineKeyboardButton("返回用户列表", callback_data="admin_list_1")],
        [InlineKeyboardButton("调整积分", callback_data=f"admin_adjust_{user.user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    await query.answer()

async def admin_adjust_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理调整积分回调"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # 检查是否是管理员
    if user_id not in ADMIN_IDS:
        await query.answer("您没有管理员权限")
        return
    
    # 从回调数据中提取用户ID
    match = re.match(r"admin_adjust_(\d+)", query.data)
    if not match:
        await query.answer("无效的回调数据")
        return
    
    target_user_id = int(match.group(1))
    
    # 获取用户信息
    storage = Storage()
    user = storage.get_user(target_user_id)
    
    if not user:
        await query.answer("找不到该用户")
        return
    
    # 保存目标用户ID到上下文
    context.user_data['adjust_target_user_id'] = target_user_id
    
    # 构建消息
    username = user.username or "无用户名"
    message = f"👤 <b>调整用户积分</b>\n\n"
    message += f"用户: {username}\n"
    message += f"ID: {user.user_id}\n"
    message += f"当前积分: {user.points}\n\n"
    message += "请选择要调整的积分数量:"
    
    # 创建积分调整按钮
    keyboard = [
        [
            InlineKeyboardButton("+10", callback_data=f"adjust_points_{target_user_id}_10"),
            InlineKeyboardButton("+50", callback_data=f"adjust_points_{target_user_id}_50"),
            InlineKeyboardButton("+100", callback_data=f"adjust_points_{target_user_id}_100")
        ],
        [
            InlineKeyboardButton("-10", callback_data=f"adjust_points_{target_user_id}_-10"),
            InlineKeyboardButton("-50", callback_data=f"adjust_points_{target_user_id}_-50"),
            InlineKeyboardButton("-100", callback_data=f"adjust_points_{target_user_id}_-100")
        ],
        [InlineKeyboardButton("返回用户详情", callback_data=f"admin_info_{target_user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    await query.answer()

async def adjust_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理积分调整回调"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # 检查是否是管理员
    if user_id not in ADMIN_IDS:
        await query.answer("您没有管理员权限")
        return
    
    # 从回调数据中提取用户ID和积分数量
    match = re.match(r"adjust_points_(\d+)_(-?\d+)", query.data)
    if not match:
        await query.answer("无效的回调数据")
        return
    
    target_user_id = int(match.group(1))
    points_change = int(match.group(2))
    
    # 获取用户信息
    storage = Storage()
    user = storage.get_user(target_user_id)
    
    if not user:
        await query.answer("找不到该用户")
        return
    
    # 调整积分
    old_points = user.points
    user.points += points_change
    
    # 确保积分不为负数
    if user.points < 0:
        user.points = 0
    
    # 保存用户数据
    storage.save_user(user)
    
    # 记录积分交易
    transaction_type = PointsTransactionType.ADMIN_ADJUSTMENT
    description = f"管理员调整 ({query.from_user.username or query.from_user.id})"
    storage.add_points_transaction(
        user_id=target_user_id,
        amount=points_change,
        transaction_type=transaction_type,
        description=description
    )
    
    # 构建消息
    username = user.username or "无用户名"
    message = f"✅ <b>积分已调整</b>\n\n"
    message += f"用户: {username}\n"
    message += f"ID: {user.user_id}\n"
    message += f"原积分: {old_points}\n"
    message += f"调整: {'+' if points_change > 0 else ''}{points_change}\n"
    message += f"新积分: {user.points}\n"
    
    # 创建按钮
    keyboard = [
        [InlineKeyboardButton("继续调整", callback_data=f"admin_adjust_{target_user_id}")],
        [InlineKeyboardButton("返回用户详情", callback_data=f"admin_info_{target_user_id}")],
        [InlineKeyboardButton("返回用户列表", callback_data="admin_list_1")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    await query.answer("积分已调整")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消当前操作"""
    await update.message.reply_text(
        "❌ 操作已取消",
        parse_mode=ParseMode.HTML
    )
    context.user_data.clear()
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看系统统计信息"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔️ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 获取存储对象
    storage = Storage()
    
    # 获取用户统计
    users = storage.users
    total_users = len(users)
    verified_users = sum(1 for user in users.values() if user.email_verified)
    
    # 获取积分统计
    total_points = sum(user.points for user in users.values())
    avg_points = total_points / total_users if total_users > 0 else 0
    max_points_user = max(users.values(), key=lambda x: x.points) if users else None
    
    # 获取签到统计
    checkins = storage.checkin_records
    total_checkins = len(checkins)
    today_checkins = sum(1 for c in checkins if c.checkin_date == datetime.now().date())
    
    # 获取交易统计
    transactions = storage.transactions
    total_transactions = len(transactions)
    
    # 获取群组统计
    groups = storage.groups
    total_groups = len(groups)
    
    # 获取邮箱验证统计
    email_verifications = storage.email_verifications
    total_verifications = len(email_verifications)
    verified_count = sum(1 for v in email_verifications.values() if v.is_verified)
    
    # 构建统计信息消息
    message = f"📊 <b>系统统计信息</b>\n\n"
    
    message += "<b>用户统计</b>\n"
    message += f"👥 总用户数: {total_users}\n"
    message += f"📧 已验证邮箱: {verified_users} ({verified_users/total_users*100:.1f}% 的用户)\n"
    message += f"📅 今日新增: {sum(1 for u in users.values() if u.join_date.date() == datetime.now().date())}\n\n"
    
    message += "<b>积分统计</b>\n"
    message += f"💰 总积分: {total_points}\n"
    message += f"📊 平均积分: {avg_points:.1f}\n"
    if max_points_user:
        message += f"🏆 最高积分: {max_points_user.points} (用户: {max_points_user.username or max_points_user.user_id})\n\n"
    
    message += "<b>签到统计</b>\n"
    message += f"✅ 总签到次数: {total_checkins}\n"
    message += f"📆 今日签到: {today_checkins}\n"
    message += f"📈 签到率: {today_checkins/total_users*100:.1f}% 的用户\n\n" if total_users > 0 else "📈 签到率: 0.0% 的用户\n\n"
    
    message += "<b>交易统计</b>\n"
    message += f"🔄 总交易数: {total_transactions}\n"
    
    # 按类型统计交易
    transaction_types = {}
    for tx in transactions:
        tx_type = tx.transaction_type
        if tx_type not in transaction_types:
            transaction_types[tx_type] = 0
        transaction_types[tx_type] += 1
    
    # 显示前5种最常见的交易类型
    sorted_types = sorted(transaction_types.items(), key=lambda x: x[1], reverse=True)[:5]
    for tx_type, count in sorted_types:
        message += f"- {tx_type}: {count} 次\n"
    message += "\n"
    
    message += "<b>群组统计</b>\n"
    message += f"👥 总群组数: {total_groups}\n"
    for group_id, group in groups.items():
        message += f"- {group.group_name}: {group.required_points} 积分\n"
    message += "\n"
    
    message += "<b>邮箱验证统计</b>\n"
    message += f"📧 总验证请求: {total_verifications}\n"
    if total_verifications > 0:
        message += f"✅ 成功验证: {verified_count} ({verified_count/total_verifications*100:.1f}% 的请求)\n\n"
    else:
        message += f"✅ 成功验证: 0 (0.0% 的请求)\n\n"
    
    message += "<b>系统信息</b>\n"
    message += f"🕒 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    message += f"💾 数据目录: {DATA_DIR}\n"
    
    # 获取数据文件大小
    data_files = [
        os.path.join(DATA_DIR, "users.json"),
        os.path.join(DATA_DIR, "checkin_records.json"),
        os.path.join(DATA_DIR, "transactions.json"),
        os.path.join(DATA_DIR, "groups.json"),
        os.path.join(DATA_DIR, "email_verifications.json")
    ]
    
    total_size = 0
    for file_path in data_files:
        if os.path.exists(file_path):
            total_size += os.path.getsize(file_path)
    
    message += f"📁 数据大小: {total_size / 1024:.1f} KB\n"
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML
    )

def get_admin_handlers() -> List[BaseHandler]:
    """返回管理员命令处理器列表"""
    return [
        # 群组管理
        ConversationHandler(
            entry_points=[CommandHandler("admin_group_add", admin_group_add)],
            states={
                WAITING_FOR_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_name_input)],
                WAITING_FOR_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, points_input)],
                WAITING_FOR_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, days_input)]
            },
            fallbacks=[CommandHandler("cancel", cancel_command)]
        ),
        
        CommandHandler("admin_group_remove", admin_group_remove),
        CommandHandler("admin_group_list", admin_group_list),
        
        # 用户管理
        CommandHandler("admin_points", admin_points),
        CommandHandler("admin_list", admin_list),
        CommandHandler("admin_info", admin_info),
        
        # 系统管理
        CommandHandler("admin_stats", admin_stats),
        
        # 回调处理
        CallbackQueryHandler(admin_list_callback, pattern=r"^admin_list_\d+$"),
        CallbackQueryHandler(admin_info_callback, pattern=r"^admin_info_\d+$"),
        CallbackQueryHandler(admin_adjust_callback, pattern=r"^admin_adjust_\d+$"),
        CallbackQueryHandler(adjust_points_callback, pattern=r"^adjust_points_\d+_-?\d+$"),
    ] 