"""
@description: 积分功能模块，处理积分查询、赠送和接受等功能
"""
import logging
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List, Union
import uuid

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    User as TelegramUser, Message, CallbackQuery
)
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, Application
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, Forbidden

from ..config.settings import (
    GIFT_EXPIRY_HOURS, MIN_GIFT_AMOUNT, MAX_GIFT_AMOUNT
)
from ..config.constants import TEMPLATES
from ..database.storage import Storage
from ..database.models import (
    User, PointsTransaction, PointsTransactionType, TransactionStatus
)

logger = logging.getLogger(__name__)

# 赠送积分的正则表达式模式
# 格式1: 赠送 @username 100 感谢分享
GIFT_PATTERN_USERNAME = r'^赠送\s+@(\w+)\s+(\d+)(?:\s+(.+))?$'
# 格式2: 赠送 100 感谢帮忙 (回复消息时)
GIFT_PATTERN_REPLY = r'^赠送\s+(\d+)(?:\s+(.+))?$'

# 存储待处理的赠送交易
# 格式: {transaction_id: {sender_id, receiver_id, amount, reason, message_id, chat_id, expires_at}}
pending_transactions: Dict[str, Dict[str, Any]] = {}

# 存储待确认的赠送请求
# 格式: {confirm_id: {sender_id, receiver_id, amount, reason, chat_id, sender_username, receiver_username}}
pending_confirmations: Dict[str, Dict[str, Any]] = {}

def format_number(number: int) -> str:
    """
    @description: 格式化数字，添加千位分隔符
    @param {int} number: 要格式化的数字
    @return {str}: 格式化后的数字字符串
    """
    return f"{number:,}"

async def handle_gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理赠送积分命令
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    message = update.effective_message
    sender = update.effective_user
    
    # 检查是否是私聊
    if update.effective_chat.type == "private":
        await message.reply_text("❌ 赠送积分功能仅在群组中可用")
        return
    
    # 获取消息文本
    text = message.text.strip()
    
    # 尝试匹配两种格式
    username_match = re.match(GIFT_PATTERN_USERNAME, text)
    reply_match = re.match(GIFT_PATTERN_REPLY, text)
    
    # 初始化变量
    receiver_username = None
    receiver_id = None
    amount = 0
    reason = "无"
    
    # 处理@用户名格式
    if username_match:
        receiver_username = username_match.group(1)
        amount = int(username_match.group(2))
        reason = username_match.group(3) or "无"
        
        # 获取存储对象
        storage = Storage()
        
        # 查找接收者
        receiver_user = None
        for user in storage.users.values():
            if user.username and user.username.lower() == receiver_username.lower():
                receiver_user = user
                break
        
        if not receiver_user:
            # 尝试在当前聊天中查找用户
            chat_members = None
            try:
                chat_members = await context.bot.get_chat_administrators(update.effective_chat.id)
            except Exception as e:
                logger.error(f"获取聊天成员失败: {e}")
            
            if chat_members:
                for member in chat_members:
                    if member.user.username and member.user.username.lower() == receiver_username.lower():
                        # 创建新用户
                        receiver_user = User(
                            user_id=member.user.id,
                            username=member.user.username,
                            join_date=datetime.now(),
                            points=0
                        )
                        storage.save_user(receiver_user)
                        break
            
            if not receiver_user:
                await message.reply_text(f"❌ 找不到用户 @{receiver_username}")
                return
        
        receiver_id = receiver_user.user_id
        receiver_username = receiver_user.username
        
    # 处理回复消息格式
    elif reply_match and message.reply_to_message:
        amount = int(reply_match.group(1))
        reason = reply_match.group(2) or "无备注"
        
        # 获取被回复的用户
        replied_to = message.reply_to_message.from_user
        if not replied_to or replied_to.is_bot:
            await message.reply_text("❌ 无法赠送积分给机器人")
            return
        
        receiver_id = replied_to.id
        receiver_username = replied_to.username or replied_to.first_name
        
    else:
        # 格式不匹配
        await message.reply_text(
            "❌ 格式错误\n\n"
            "正确格式:\n"
            "- 赠送 @用户名 数量 [备注]\n"
            "- 回复某人消息并发送: 赠送 数量 [备注]"
        )
        return
    
    # 验证积分数量
    if amount < MIN_GIFT_AMOUNT:
        await message.reply_text(f"❌ 最小赠送积分数量为 {MIN_GIFT_AMOUNT}")
        return
    
    if amount > MAX_GIFT_AMOUNT:
        await message.reply_text(f"❌ 最大赠送积分数量为 {format_number(MAX_GIFT_AMOUNT)}")
        return
    
    # 检查是否自赠
    if sender.id == receiver_id:
        await message.reply_text("❌ 不能给自己赠送积分")
        return
    
    # 获取存储对象
    storage = Storage()
    
    # 获取赠送者
    sender_user = storage.get_user(sender.id)
    if not sender_user:
        # 创建新用户
        sender_user = User(
            user_id=sender.id,
            username=sender.username or sender.first_name,
            join_date=datetime.now(),
            points=0
        )
        storage.save_user(sender_user)
    
    # 检查积分是否足够
    if sender_user.points < amount:
        await message.reply_text(
            TEMPLATES["insufficient_points"].format(
                current_points=format_number(sender_user.points),
                amount=format_number(amount)
            ),
            parse_mode=ParseMode.HTML
        )
        return
    
    # 创建确认ID
    confirm_id = str(uuid.uuid4())
    
    # 存储确认信息
    pending_confirmations[confirm_id] = {
        "sender_id": sender.id,
        "receiver_id": receiver_id,
        "amount": amount,
        "reason": reason,
        "chat_id": update.effective_chat.id,
        "sender_username": sender.username or sender.first_name,
        "receiver_username": receiver_username
    }
    
    # 创建确认按钮
    keyboard = [
        [
            InlineKeyboardButton("✅ 确认", callback_data=f"confirm_{confirm_id}"),
            InlineKeyboardButton("❌ 取消", callback_data=f"cancel_{confirm_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 发送确认消息
    await message.reply_text(
        TEMPLATES["gift_confirm_request"].format(
            receiver_username=receiver_username,
            amount=format_number(amount),
            reason=reason,
            sender_points=format_number(sender_user.points)
        ),
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    logger.info(f"用户 {sender.username or sender.first_name} (ID: {sender.id}) 请求向 {receiver_username} (ID: {receiver_id}) 赠送 {amount} 积分，原因: {reason}")

async def handle_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理确认交易的回调"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # 跳过恢复相关的回调，避免干扰recover.py
    if query.data.startswith("confirm_recovery_"):
        logger.debug(f"跳过处理恢复相关的回调: {query.data}")
        return
    
    # 获取回调数据
    callback_data = query.data
    
    # 解析回调数据
    action, confirm_id = callback_data.split("_", 1)
    
    # 检查确认是否存在
    if confirm_id not in pending_confirmations:
        await query.answer("❌ 该确认已不存在或已过期")
        return
    
    # 获取确认信息
    confirm_info = pending_confirmations[confirm_id]
    
    # 检查是否是赠送者
    if user_id != confirm_info["sender_id"]:
        await query.answer("❌ 只有赠送者才能确认或取消赠送")
        return
    
    if action == "confirm":
        # 确认赠送
        await process_gift(
            update, context, 
            confirm_info["sender_id"], 
            confirm_info["receiver_id"], 
            confirm_info["amount"], 
            confirm_info["reason"], 
            confirm_info["sender_username"],
            confirm_info["receiver_username"]
        )
        
        # 更新确认消息
        await query.edit_message_text(
            f"✅ 已确认赠送 {format_number(confirm_info['amount'])} 积分给 {confirm_info['receiver_username']}，请等待对方接受。",
            parse_mode=ParseMode.HTML
        )
    
    elif action == "cancel":
        # 取消赠送
        await query.edit_message_text(
            TEMPLATES["gift_canceled"].format(
                receiver_username=confirm_info["receiver_username"],
                amount=format_number(confirm_info["amount"])
            ),
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"用户 {confirm_info['sender_username']} (ID: {confirm_info['sender_id']}) 取消了向 {confirm_info['receiver_username']} (ID: {confirm_info['receiver_id']}) 赠送 {confirm_info['amount']} 积分")
    
    # 删除确认信息
    del pending_confirmations[confirm_id]
    
    # 回答回调查询
    await query.answer()

async def process_gift(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    sender_id: int, 
    receiver_id: int, 
    amount: int, 
    reason: str,
    sender_username: str,
    receiver_username: str
) -> None:
    """
    @description: 处理赠送积分请求
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    @param {int} sender_id: 赠送者ID
    @param {int} receiver_id: 接收者ID
    @param {int} amount: 积分数量
    @param {str} reason: 赠送备注
    @param {str} sender_username: 赠送者用户名
    @param {str} receiver_username: 接收者用户名
    """
    # 获取存储对象
    storage = Storage()
    
    # 获取赠送者
    sender = storage.get_user(sender_id)
    if not sender:
        # 创建新用户
        sender = User(
            user_id=sender_id,
            username=sender_username,
            join_date=datetime.now(),
            points=0
        )
        storage.save_user(sender)
    
    # 获取接收者
    receiver = storage.get_user(receiver_id)
    if not receiver:
        # 创建新用户
        receiver = User(
            user_id=receiver_id,
            username=receiver_username,
            join_date=datetime.now(),
            points=0
        )
        storage.save_user(receiver)
    
    # 检查积分是否足够
    if sender.points < amount:
        if isinstance(update.callback_query, CallbackQuery):
            await update.callback_query.edit_message_text(
                TEMPLATES["insufficient_points"].format(
                    current_points=format_number(sender.points),
                    amount=format_number(amount)
                ),
                parse_mode=ParseMode.HTML
            )
        else:
            await update.effective_message.reply_text(
                TEMPLATES["insufficient_points"].format(
                    current_points=format_number(sender.points),
                    amount=format_number(amount)
                ),
                parse_mode=ParseMode.HTML
            )
        return
    
    # 冻结赠送者的积分
    sender.points -= amount
    sender.frozen_points += amount
    storage.save_user(sender)
    
    # 创建交易记录
    transaction_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(hours=GIFT_EXPIRY_HOURS)
    
    # 存储交易
    transaction = PointsTransaction(
        user_id=sender_id,
        amount=-amount,
        transaction_type=PointsTransactionType.GIFT_SENT,
        description=f"赠送给 {receiver_username}: {reason}",
        related_user_id=receiver_id,
        transaction_id=transaction_id,
        status=TransactionStatus.PENDING,
        expires_at=expires_at
    )
    storage.add_transaction(transaction)
    
    # 创建接收按钮
    keyboard = [
        [
            InlineKeyboardButton("✅ 接受", callback_data=f"accept_{transaction_id}"),
            InlineKeyboardButton("❌ 拒绝", callback_data=f"reject_{transaction_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 在群组中发送通知消息（不包含接受/拒绝按钮）
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🎁 {sender_username} → {receiver_username}: {format_number(amount)} 积分",
        parse_mode=ParseMode.HTML
    )
    
    # 向接收者发送私聊通知，包含接受/拒绝按钮
    try:
        message = await context.bot.send_message(
            chat_id=receiver_id,
            text=TEMPLATES["gift_request"].format(
                sender_username=sender_username,
                amount=format_number(amount),
                reason=reason,
                expiry_hours=GIFT_EXPIRY_HOURS
            ),
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        # 存储交易信息，注意这里的message_id和chat_id是接收者的私聊消息
        pending_transactions[transaction_id] = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "amount": amount,
            "reason": reason,
            "message_id": message.message_id,
            "chat_id": receiver_id,  # 接收者的用户ID作为chat_id
            "expires_at": expires_at,
            "sender_username": sender_username,
            "receiver_username": receiver_username
        }
        
        logger.info(f"成功向用户 {receiver_username} (ID: {receiver_id}) 发送积分赠送私聊通知")
    except (BadRequest, Forbidden) as e:
        # 用户可能未启动与机器人的对话，或从未使用过机器人
        logger.warning(f"无法向用户 {receiver_username} (ID: {receiver_id}) 发送私聊通知: {str(e)}")
        
        # 在群组中发送提醒通知
        if isinstance(e, Forbidden):
            # Forbidden错误 - 用户从未使用过机器人
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ <b>积分发送提醒</b>\n\n@{receiver_username} 似乎还从未使用过本机器人 [@{context.bot.username}]\n\n积分已退还给 {sender_username}。",
                parse_mode=ParseMode.HTML
            )
        else:
            # BadRequest错误 - 其他原因导致无法发送
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ <b>通知发送失败</b>\n\n无法向 @{receiver_username} 发送私聊通知，请让对方先与机器人 [@{context.bot.username}] 开始对话。\n\n积分已退还给 {sender_username}。",
                parse_mode=ParseMode.HTML
            )
        
        # 解冻并返还积分
        sender.points += amount
        sender.frozen_points -= amount
        storage.save_user(sender)
        
        # 更新交易状态
        transaction.status = TransactionStatus.CANCELLED
        storage.add_transaction(transaction)
        
        return
    
    # 设置过期任务
    context.job_queue.run_once(
        check_expired_transaction,
        GIFT_EXPIRY_HOURS * 3600,
        data=transaction_id
    )
    
    logger.info(f"用户 {sender_username} (ID: {sender_id}) 向 {receiver_username} (ID: {receiver_id}) 赠送了 {amount} 积分，原因: {reason}")

async def handle_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理赠送积分回调
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    query = update.callback_query
    user_id = query.from_user.id
    
    # 获取回调数据
    callback_data = query.data
    
    # 解析回调数据
    action, transaction_id = callback_data.split("_", 1)
    
    # 检查交易是否存在
    if transaction_id not in pending_transactions:
        await query.answer("❌ 该交易已不存在或已过期")
        return
    
    # 获取交易信息
    transaction_info = pending_transactions[transaction_id]
    
    # 检查是否是接收者
    if user_id != transaction_info["receiver_id"]:
        await query.answer("❌ 只有接收者才能接受或拒绝赠送")
        return
    
    # 检查是否在私聊中操作
    if query.message.chat.type != "private":
        await query.answer("❌ 请在与机器人的私聊中操作")
        return
    
    # 获取存储对象
    storage = Storage()
    
    # 获取赠送者和接收者
    sender = storage.get_user(transaction_info["sender_id"])
    receiver = storage.get_user(transaction_info["receiver_id"])
    
    if action == "accept":
        # 接受赠送
        await accept_gift(query, context, transaction_id, sender, receiver, transaction_info)
    elif action == "reject":
        # 拒绝赠送
        await reject_gift(query, context, transaction_id, sender, receiver, transaction_info)

async def accept_gift(
    query: CallbackQuery, 
    context: ContextTypes.DEFAULT_TYPE,
    transaction_id: str, 
    sender: User, 
    receiver: User, 
    transaction_info: Dict[str, Any]
) -> None:
    """
    @description: 接受赠送
    @param {CallbackQuery} query: 回调查询对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    @param {str} transaction_id: 交易ID
    @param {User} sender: 赠送者
    @param {User} receiver: 接收者
    @param {Dict[str, Any]} transaction_info: 交易信息
    """
    # 获取存储对象
    storage = Storage()
    
    # 解冻赠送者的积分
    sender.frozen_points -= transaction_info["amount"]
    storage.save_user(sender)
    
    # 增加接收者的积分
    receiver.points += transaction_info["amount"]
    storage.save_user(receiver)
    
    # 更新交易状态
    transaction = next((t for t in storage.transactions if t.transaction_id == transaction_id), None)
    if transaction:
        transaction.status = TransactionStatus.COMPLETED
        storage.add_transaction(transaction)
    
    # 创建接收者的交易记录
    receiver_transaction = PointsTransaction(
        user_id=receiver.user_id,
        amount=transaction_info["amount"],
        transaction_type=PointsTransactionType.GIFT_RECEIVED,
        description=f"收到来自 {transaction_info['sender_username']} 的赠送: {transaction_info['reason']}",
        related_user_id=sender.user_id,
        transaction_id=str(uuid.uuid4()),
        status=TransactionStatus.COMPLETED
    )
    storage.add_transaction(receiver_transaction)
    
    # 更新消息
    try:
        await query.edit_message_text(
            TEMPLATES["gift_accepted"].format(
                sender_username=transaction_info["sender_username"],
                receiver_username=transaction_info["receiver_username"],
                amount=format_number(transaction_info["amount"]),
                reason=transaction_info["reason"],
                receiver_points=format_number(receiver.points)
            ),
            parse_mode=ParseMode.HTML
        )
    except BadRequest:
        # 消息可能已被删除
        pass
    
    # 通知赠送者
    try:
        await context.bot.send_message(
            chat_id=sender.user_id,
            text=TEMPLATES["gift_success"].format(
                sender_username=transaction_info["sender_username"],
                receiver_username=transaction_info["receiver_username"],
                amount=format_number(transaction_info["amount"]),
                reason=transaction_info["reason"],
                sender_points=format_number(sender.points)
            ),
            parse_mode=ParseMode.HTML
        )
    except BadRequest:
        # 用户可能未启动与机器人的对话
        pass
    
    # 通知接收者
    try:
        await context.bot.send_message(
            chat_id=receiver.user_id,
            text=TEMPLATES["gift_received"].format(
                sender_username=transaction_info["sender_username"],
                receiver_username=transaction_info["receiver_username"],
                amount=format_number(transaction_info["amount"]),
                reason=transaction_info["reason"],
                receiver_points=format_number(receiver.points)
            ),
            parse_mode=ParseMode.HTML
        )
    except BadRequest:
        # 用户可能未启动与机器人的对话
        logger.info(f"无法向用户 {receiver.username} (ID: {receiver.user_id}) 发送积分接收通知")
    
    # 删除交易信息
    del pending_transactions[transaction_id]
    
    # 回答回调查询
    await query.answer("✅ 已接受积分赠送")
    
    logger.info(f"用户 {receiver.username} (ID: {receiver.user_id}) 接受了来自 {sender.username} (ID: {sender.user_id}) 的 {transaction_info['amount']} 积分赠送")

async def reject_gift(
    query: CallbackQuery, 
    context: ContextTypes.DEFAULT_TYPE,
    transaction_id: str, 
    sender: User, 
    receiver: User, 
    transaction_info: Dict[str, Any]
) -> None:
    """
    @description: 拒绝赠送
    @param {CallbackQuery} query: 回调查询对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    @param {str} transaction_id: 交易ID
    @param {User} sender: 赠送者
    @param {User} receiver: 接收者
    @param {Dict[str, Any]} transaction_info: 交易信息
    """
    # 获取存储对象
    storage = Storage()
    
    # 解冻并返还赠送者的积分
    sender.frozen_points -= transaction_info["amount"]
    sender.points += transaction_info["amount"]
    storage.save_user(sender)
    
    # 更新交易状态
    transaction = next((t for t in storage.transactions if t.transaction_id == transaction_id), None)
    if transaction:
        transaction.status = TransactionStatus.REJECTED
        storage.add_transaction(transaction)
    
    # 更新消息
    try:
        await query.edit_message_text(
            TEMPLATES["gift_rejected"].format(
                sender_username=transaction_info["sender_username"],
                receiver_username=transaction_info["receiver_username"],
                amount=format_number(transaction_info["amount"]),
                reason=transaction_info["reason"]
            ),
            parse_mode=ParseMode.HTML
        )
    except BadRequest:
        # 消息可能已被删除
        pass
    
    # 通知赠送者
    try:
        await context.bot.send_message(
            chat_id=sender.user_id,
            text=TEMPLATES["gift_rejected"].format(
                sender_username=transaction_info["sender_username"],
                receiver_username=transaction_info["receiver_username"],
                amount=format_number(transaction_info["amount"]),
                reason=transaction_info["reason"]
            ),
            parse_mode=ParseMode.HTML
        )
    except BadRequest:
        # 用户可能未启动与机器人的对话
        pass
    
    # 删除交易信息
    del pending_transactions[transaction_id]
    
    # 回答回调查询
    await query.answer("❌ 已拒绝积分赠送")
    
    logger.info(f"用户 {receiver.username} (ID: {receiver.user_id}) 拒绝了来自 {sender.username} (ID: {sender.user_id}) 的 {transaction_info['amount']} 积分赠送")

async def check_expired_transaction(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 检查过期交易
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    transaction_id = context.job.data
    
    # 检查交易是否存在
    if transaction_id not in pending_transactions:
        return
    
    # 获取交易信息
    transaction_info = pending_transactions[transaction_id]
    
    # 检查是否已过期
    now = datetime.now()
    if now < transaction_info["expires_at"]:
        return
    
    # 获取存储对象
    storage = Storage()
    
    # 获取赠送者
    sender = storage.get_user(transaction_info["sender_id"])
    if not sender:
        logger.error(f"无法找到赠送者 (ID: {transaction_info['sender_id']})")
        return
    
    # 获取接收者
    receiver = storage.get_user(transaction_info["receiver_id"])
    if not receiver:
        logger.error(f"无法找到接收者 (ID: {transaction_info['receiver_id']})")
        return
    
    # 解冻并返还赠送者的积分
    sender.frozen_points -= transaction_info["amount"]
    sender.points += transaction_info["amount"]
    storage.save_user(sender)
    
    # 更新交易状态
    transaction = next((t for t in storage.transactions if t.transaction_id == transaction_id), None)
    if transaction:
        transaction.status = TransactionStatus.EXPIRED
        storage.add_transaction(transaction)
    
    # 更新消息
    try:
        await context.bot.edit_message_text(
            chat_id=transaction_info["chat_id"],
            message_id=transaction_info["message_id"],
            text=TEMPLATES["gift_expired"].format(
                sender_username=transaction_info["sender_username"],
                receiver_username=transaction_info["receiver_username"],
                amount=format_number(transaction_info["amount"]),
                reason=transaction_info["reason"],
                expiry_hours=GIFT_EXPIRY_HOURS
            ),
            parse_mode=ParseMode.HTML
        )
    except BadRequest:
        # 消息可能已被删除
        pass
    
    # 通知赠送者
    try:
        await context.bot.send_message(
            chat_id=sender.user_id,
            text=TEMPLATES["gift_expired"].format(
                sender_username=transaction_info["sender_username"],
                receiver_username=transaction_info["receiver_username"],
                amount=format_number(transaction_info["amount"]),
                reason=transaction_info["reason"],
                expiry_hours=GIFT_EXPIRY_HOURS
            ),
            parse_mode=ParseMode.HTML
        )
    except BadRequest:
        # 用户可能未启动与机器人的对话
        pass
    
    # 删除交易信息
    del pending_transactions[transaction_id]
    
    logger.info(f"交易 {transaction_id} 已过期，积分已退还给 {sender.username} (ID: {sender.user_id})")

async def points_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理/points命令，查询积分
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    user = update.effective_user
    storage = Storage()
    
    # 获取用户
    db_user = storage.get_user(user.id)
    if not db_user:
        db_user = User(
            user_id=user.id,
            username=user.username or user.first_name,
            join_date=datetime.now(),
            points=0
        )
        storage.save_user(db_user)
    
    # 创建分类按钮
    keyboard = [
        [
            InlineKeyboardButton("💰 积分概览", callback_data="points_overview"),
            InlineKeyboardButton("📊 积分统计", callback_data="points_stats")
        ],
        [
            InlineKeyboardButton("🔄 交易记录", callback_data="points_transactions"),
            InlineKeyboardButton("🎁 赠送记录", callback_data="points_gifts")
        ],
        [
            InlineKeyboardButton("📝 签到", callback_data="checkin_shortcut"),
            InlineKeyboardButton("🔄 刷新", callback_data="refresh_points")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查是否为话题消息
    message = update.message
    is_topic = getattr(message, 'is_topic_message', False)
    thread_id = getattr(message, 'message_thread_id', None)
    
    # 发送初始消息
    if is_topic and thread_id:
        # 在话题群组中回复，使用相同的话题ID
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            message_thread_id=thread_id,
            text=f"👋 欢迎 {user.username or user.first_name}！\n"
            f"💰 当前积分：<code>{format_number(db_user.points)}</code>\n\n"
            "请选择要查看的内容：",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        # 普通消息回复
        await update.message.reply_text(
            f"👋 欢迎 {user.username or user.first_name}！\n"
            f"💰 当前积分：<code>{format_number(db_user.points)}</code>\n\n"
            "请选择要查看的内容：",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

async def handle_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理积分相关的回调查询
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        # 获取存储对象
        storage = Storage()
        user = storage.get_user(user_id)
        
        if not user:
            await query.answer("❌ 用户数据不存在")
            return
        
        # 获取回调数据
        callback_data = query.data
        
        # 创建基础键盘
        keyboard = [
            [
                InlineKeyboardButton("💰 积分概览", callback_data="points_overview"),
                InlineKeyboardButton("📊 积分统计", callback_data="points_stats")
            ],
            [
                InlineKeyboardButton("🔄 交易记录", callback_data="points_transactions"),
                InlineKeyboardButton("🎁 赠送记录", callback_data="points_gifts")
            ],
            [
                InlineKeyboardButton("✅ 签到", callback_data="checkin_shortcut"),
                InlineKeyboardButton("🔄 刷新", callback_data="refresh_points")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if callback_data == "points_overview":
            # 获取用户的积分概览
            text = TEMPLATES["points_overview"].format(
                username=user.username,
                points=format_number(user.points),
                frozen_points=format_number(user.frozen_points),
                total_checkins=format_number(user.total_checkins),
                monthly_checkins=format_number(user.monthly_checkins),
                streak_days=user.streak_days
            )
        
        elif callback_data == "points_stats":
            # 获取用户的积分统计
            text = TEMPLATES["points_stats"].format(
                username=user.username,
                streak_days=user.streak_days,
                max_streak_days=user.max_streak_days,
                total_checkins=format_number(user.total_checkins),
                monthly_checkins=format_number(user.monthly_checkins)
            )
        
        elif callback_data == "points_transactions":
            # 获取最近的交易记录
            transactions = storage.get_user_transactions(user_id, limit=10)
            if not transactions:
                text = "📝 暂无交易记录"
            else:
                text = "📝 最近的交易记录：\n\n"
                for tx in transactions:
                    icon = "➕" if tx.amount > 0 else "➖"
                    text += f"{icon} {tx.description}: {format_number(abs(tx.amount))} 积分\n"
                    text += f"时间: {tx.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        elif callback_data == "points_gifts":
            # 获取最近的赠送记录
            gifts = storage.get_user_gift_transactions(user_id, limit=10)
            if not gifts:
                text = "🎁 暂无赠送记录"
            else:
                text = "🎁 最近的赠送记录：\n\n"
                for gift in gifts:
                    if gift.transaction_type == PointsTransactionType.GIFT_SENT:
                        text += f"➖ {gift.description}\n"
                    else:
                        text += f"➕ {gift.description}\n"
                    text += f"时间: {gift.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        elif callback_data == "checkin_shortcut":
            # 快捷签到
            from .checkin import handle_checkin_command
            await handle_checkin_command(update, context)
            return
        
        elif callback_data == "refresh_points":
            # 刷新积分信息
            # 重新从存储中获取用户数据
            storage = Storage()
            user = storage.get_user(user_id)
            if not user:
                await query.answer("❌ 用户数据不存在")
                return
                
            text = TEMPLATES["points_info"].format(
                username=user.username,
                points=format_number(user.points),
                frozen_points=format_number(user.frozen_points)
            )
        
        else:
            await query.answer("❌ 未知的回调类型")
            return
        
        try:
            # 检查消息内容是否相同
            current_text = query.message.text
            if current_text == text:
                await query.answer("数据已是最新")
                return
            
            # 更新消息
            await query.message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            
        except NetworkError:
            logger.error("网络连接错误")
            await query.answer("❌ 网络连接错误，请重试")
            
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("数据已是最新")
            else:
                logger.error(f"更新消息失败: {e}")
                await query.answer("❌ 更新消息失败，请重试")
                
    except Exception as e:
        logger.error(f"处理积分回调时出错: {e}")
        await query.answer("❌ 处理请求时出错，请重试")

def get_back_keyboard() -> InlineKeyboardMarkup:
    """
    @description: 获取返回主菜单的键盘
    @return {InlineKeyboardMarkup}: 键盘标记
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ 返回", callback_data="back_to_menu")]
    ])

def register_handlers(application: Application) -> None:
    """
    @description: 注册积分功能相关的处理器
    @param {Application} application: 应用程序实例
    """
    # 注册积分查询命令
    application.add_handler(CommandHandler("points", points_command))
    
    # 注册赠送积分消息处理器
    application.add_handler(MessageHandler(
        filters.Regex(GIFT_PATTERN_USERNAME) | filters.Regex(GIFT_PATTERN_REPLY),
        handle_gift_command
    ))
    
    # 注册积分相关的回调查询处理器
    application.add_handler(CallbackQueryHandler(handle_points_callback, pattern="^points_overview$"))
    application.add_handler(CallbackQueryHandler(handle_points_callback, pattern="^points_stats$"))
    application.add_handler(CallbackQueryHandler(handle_points_callback, pattern="^points_transactions$"))
    application.add_handler(CallbackQueryHandler(handle_points_callback, pattern="^points_gifts$"))
    application.add_handler(CallbackQueryHandler(handle_points_callback, pattern="^checkin_shortcut$"))
    application.add_handler(CallbackQueryHandler(handle_points_callback, pattern="^refresh_points$"))
    application.add_handler(CallbackQueryHandler(handle_points_callback, pattern="^back_to_menu$"))
    
    # 注册赠送确认相关的回调查询处理器
    application.add_handler(CallbackQueryHandler(handle_confirm_callback, pattern="^confirm_"))
    application.add_handler(CallbackQueryHandler(handle_cancel_callback, pattern="^cancel_"))
    application.add_handler(CallbackQueryHandler(handle_accept_callback, pattern="^accept_"))
    application.add_handler(CallbackQueryHandler(handle_reject_callback, pattern="^reject_"))
    
    logger.info("积分功能处理器注册完成")

def get_points_handlers():
    """
    @description: 获取积分相关的处理器列表
    @return {List}: 处理器列表
    """
    handlers = [
        # 积分查询命令
        CommandHandler("points", points_command),
        
        # 赠送积分处理器
        MessageHandler(
            filters.Regex(r"^赠送\s+(@\w+\s+\d+|\d+)(?:\s+.*)?$"), handle_gift_command
        ),
        MessageHandler(
            filters.Regex(r"^/gift\s+(@\w+\s+\d+|\d+)(?:\s+.*)?$"), handle_gift_command
        ),
        
        # 回调查询处理器
        CallbackQueryHandler(handle_confirm_callback, pattern=r"^(confirm|cancel)_"),
        CallbackQueryHandler(handle_gift_callback, pattern=r"^(accept|reject)_"),
        
        # 积分查询相关的回调处理器
        CallbackQueryHandler(handle_points_callback, pattern=r"^(points_overview|points_stats|points_transactions|points_gifts|back_to_menu|checkin_shortcut|refresh_points)$")
    ]
    
    return handlers 

async def get_user_points_info(user_id: int) -> str:
    """
    获取用户积分信息
    
    用于处理来自按钮回调的积分查询请求
    
    Args:
        user_id: 用户ID
        
    Returns:
        str: 包含用户积分信息的HTML格式文本
    """
    try:
        # 获取存储对象
        storage = Storage()
        
        # 获取用户信息
        user = storage.get_user(user_id)
        if not user:
            logger.warning(f"用户 ID: {user_id} 不存在")
            return "❌ 用户信息不存在，请先使用 /start 命令注册"
        
        # 获取用户的交易记录
        transactions = storage.get_user_transactions(user_id, limit=5)
        
        # 构建积分信息文本
        info_text = f"""
<b>💰 积分信息</b>

<b>当前积分</b>: {format_number(user.points)} 积分
<b>冻结积分</b>: {format_number(user.frozen_points)} 积分
<b>可用积分</b>: {format_number(user.points - user.frozen_points)} 积分

<b>积分使用提示</b>
• 可通过每日签到获得积分
• 连续签到可获得额外奖励
• 积分可用于群组权益和赠送好友
• 使用 <code>赠送 @用户名 数量 [备注]</code> 赠送积分
"""
        
        # 如果有交易记录，添加最近交易
        if transactions:
            info_text += "\n<b>最近交易记录</b>\n"
            for tx in transactions:
                tx_time = tx.created_at.strftime("%m-%d %H:%M")
                amount_str = f"+{tx.amount}" if tx.amount > 0 else f"{tx.amount}"
                desc = tx.description[:20] + "..." if len(tx.description) > 20 else tx.description
                info_text += f"• {tx_time} {amount_str} 积分 - {desc}\n"
        else:
            info_text += "\n暂无交易记录"
            
        # 添加统计信息
        total_earned = storage.get_user_total_earned(user_id)
        total_spent = storage.get_user_total_spent(user_id)
        
        info_text += f"""
<b>积分统计</b>
• 总收入: {format_number(total_earned)} 积分
• 总支出: {format_number(total_spent)} 积分
"""
        
        logger.info(f"已查询用户 ID: {user_id} 的积分信息")
        return info_text
    
    except Exception as e:
        logger.error(f"查询用户 ID: {user_id} 积分信息时出错: {e}", exc_info=True)
        return "❌ 查询积分信息时出错，请稍后再试" 