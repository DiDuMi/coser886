"""
@description: 处理邮箱绑定和验证相关的功能
"""
import logging
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, filters, 
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from coser_bot.config.settings import (
    EMAIL_VERIFICATION_EXPIRY_MINUTES, 
    MIN_POINTS_FOR_EMAIL_BINDING,
    EMAIL_VERIFICATION_BONUS
)
from coser_bot.config.constants import TEMPLATES, EmailVerifyStatus, PointsTransactionType
from coser_bot.database.storage import Storage
from coser_bot.database.models import User, EmailVerification, PointsTransaction
from coser_bot.utils.email_sender import (
    send_verification_email, 
    generate_verification_code,
    is_valid_email
)

# 创建存储实例
storage = Storage()

# 配置日志
logger = logging.getLogger(__name__)

# 定义会话状态
WAITING_FOR_EMAIL = 1
WAITING_FOR_VERIFICATION = 2

async def bind_email_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理/bind_email命令，开始邮箱绑定流程
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    user_id = update.effective_user.id
    logger.info(f"邮箱绑定命令被调用 - 用户ID: {user_id}")
    
    # 获取存储对象 - 首先尝试从context获取，如果失败则使用全局对象
    try:
        # 尝试多种可能的存储位置
        if hasattr(context, 'application') and context.application and hasattr(context.application, 'bot_data'):
            storage_obj = context.application.bot_data.get("storage")
        elif hasattr(context, 'bot_data'):
            storage_obj = context.bot_data.get("storage")
        else:
            storage_obj = None
            
        if not storage_obj:
            # 使用全局存储对象
            logger.warning(f"从context中未找到存储对象，使用全局存储对象 - 用户ID: {user_id}")
            storage_obj = storage
        
        # 强制重新加载数据
        if hasattr(storage_obj, "_load_data"):
            storage_obj._load_data()
        
        user = storage_obj.get_user(user_id)
        
        if not user:
            user = User(
                user_id=user_id,
                username=update.effective_user.username or "",
                join_date=datetime.now(),
                points=0
            )
            storage_obj.save_user(user)
        
        # 再次获取最新数据
        user = storage_obj.get_user(user_id)
            
        # 检查用户积分是否足够
        if user.points < MIN_POINTS_FOR_EMAIL_BINDING:
            logger.info(f"用户 {user_id} 积分不足，无法绑定邮箱")
            await update.message.reply_text(
                TEMPLATES["email_binding_insufficient_points"].format(
                    required_points=MIN_POINTS_FOR_EMAIL_BINDING,
                    current_points=user.points
                ),
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
            
        # 如果用户已经绑定了邮箱，询问是否要更换
        if user.email:
            logger.info(f"用户 {user_id} 已绑定邮箱: {user.email}")
            keyboard = [
                [
                    InlineKeyboardButton("是，更换邮箱", callback_data="change_email"),
                    InlineKeyboardButton("否，保持不变", callback_data="keep_email")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                TEMPLATES["email_already_bound"].format(email=user.email),
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
            
        # 如果是直接带参数的命令，如 /bind_email example@example.com
        if context.args and len(context.args) > 0:
            email = context.args[0]
            return await process_email_input(update, context, email)
        
        # 记录状态到用户数据中
        context.user_data["email_state"] = "WAITING_FOR_EMAIL"
        logger.info(f"用户 {user_id} 进入邮箱绑定流程，等待输入邮箱")
        
        # 否则提示用户输入邮箱
        await update.message.reply_text(
            TEMPLATES["email_binding_prompt"],
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_EMAIL
        
    except Exception as e:
        # 记录详细的错误信息
        logger.error(f"邮箱绑定出错 - 用户ID: {user_id}, 错误: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "系统错误，请稍后再试或联系管理员。",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

async def email_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理用户输入的邮箱
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    try:
        # 添加详细日志，记录消息接收
        user_id = update.effective_user.id
        logger.info(f"邮箱处理函数被调用 - 用户ID: {user_id}")
        
        # 检查消息是否存在
        if not update.message:
            logger.error(f"用户 {user_id} 的更新对象中没有消息")
            return ConversationHandler.END
            
        message_text = update.message.text.strip()
        logger.info(f"收到用户 {user_id} 的消息: '{message_text}'")
        
        # 处理取消命令
        if message_text.startswith('/cancel'):
            logger.info(f"用户 {user_id} 在输入邮箱阶段取消操作")
            await update.message.reply_text(
                TEMPLATES["operation_cancelled"],
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 处理用户输入的邮箱
        return await process_email_input(update, context, message_text)
    except Exception as e:
        # 记录详细的错误信息
        user_id = update.effective_user.id if update.effective_user else "未知"
        logger.error(f"处理邮箱输入时出错 - 用户ID: {user_id}, 错误: {str(e)}", exc_info=True)
        
        # 尝试发送错误消息给用户
        try:
            if update.message:
                await update.message.reply_text(
                    "处理您的邮箱时出现错误，请稍后再试或联系管理员。",
                    parse_mode=ParseMode.HTML
                )
        except Exception as send_error:
            logger.error(f"无法发送错误消息到用户 {user_id}: {str(send_error)}")
            
        return ConversationHandler.END

async def process_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE, email: str) -> int:
    """
    @description: 处理邮箱输入的核心逻辑
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @param {str} email: 用户输入的邮箱
    @return {int}: 会话状态
    """
    user_id = update.effective_user.id
    logger.info(f"处理用户 {user_id} 输入的邮箱: {email}")
    
    try:
        # 获取存储对象
        storage_obj = context.application.bot_data.get("storage")
        if not storage_obj:
            logger.error(f"无法获取存储对象 - 用户ID: {user_id}")
            await update.message.reply_text(
                "系统错误，请稍后再试或联系管理员。",
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 验证邮箱格式
        if not is_valid_email(email):
            logger.warning(f"用户 {user_id} 输入的邮箱格式不正确: {email}")
            await update.message.reply_text(
                TEMPLATES.get("invalid_email_format", "邮箱格式不正确，请重新输入正确的邮箱地址。"),
                parse_mode=ParseMode.HTML
            )
            return WAITING_FOR_EMAIL
        
        # 检查邮箱是否已被其他用户绑定
        existing_user = storage_obj.get_user_by_email(email)
        if existing_user and existing_user.user_id != update.effective_user.id:
            logger.warning(f"邮箱 {email} 已被用户 {existing_user.user_id} 绑定")
            await update.message.reply_text(
                TEMPLATES.get("email_already_bound_by_other", "该邮箱已被其他用户绑定，请使用其他邮箱。"),
                parse_mode=ParseMode.HTML
            )
            return WAITING_FOR_EMAIL
        
        # 生成验证码
        verification_code = generate_verification_code()
        logger.info(f"为用户 {user_id} 生成验证码: {verification_code}")
        
        # 创建验证记录
        verification = EmailVerification(
            user_id=user_id,
            email=email,
            verification_code=verification_code,
            status=EmailVerifyStatus.PENDING
        )
        
        success = storage_obj.add_email_verification(verification)
        if not success:
            logger.error(f"为用户 {user_id} 添加邮箱验证记录失败")
            await update.message.reply_text(
                TEMPLATES.get("system_error", "系统错误，请稍后再试或联系管理员。"),
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 发送验证邮件
        subject = "Coser Community Email Verification"
        # 使用英文内容避免编码问题
        message_content = f"Your verification code is: {verification_code}\n\nThis code will expire in {EMAIL_VERIFICATION_EXPIRY_MINUTES} minutes."
        
        logger.info(f"准备向邮箱 {email} 发送验证码 {verification_code}")
        success, message = await send_verification_email(email, subject, message_content)
        
        if not success:
            logger.error(f"向用户 {user_id} 的邮箱 {email} 发送验证码失败: {message}")
            await update.message.reply_text(
                TEMPLATES.get("send_verification_failed", "发送验证码失败，请检查邮箱地址或稍后再试。"),
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 记录邮箱到用户数据中，供后续使用
        context.user_data["pending_email"] = email
        
        # 提示用户输入验证码
        logger.info(f"向用户 {user_id} 的邮箱 {email} 发送验证码成功")
        
        # 使用重试机制发送消息
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                await update.message.reply_text(
                    TEMPLATES.get("verification_code_sent", "验证码已发送到您的邮箱 {email}，请在 {expiry_minutes} 分钟内输入验证码。如需取消操作，请发送 /cancel 命令。").format(
                        email=email,
                        expiry_minutes=EMAIL_VERIFICATION_EXPIRY_MINUTES
                    ),
                    parse_mode=ParseMode.HTML
                )
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"向用户 {user_id} 发送消息失败，已重试 {retry_count} 次: {str(e)}")
                    # 即使发送消息失败，也继续验证流程，因为验证码已经发送成功
                    pass
                else:
                    await asyncio.sleep(1)  # 等待1秒后重试
        
        return WAITING_FOR_VERIFICATION
        
    except Exception as e:
        # 记录详细的错误信息
        logger.error(f"处理邮箱 {email} 时出错 - 用户ID: {user_id}, 错误: {str(e)}", exc_info=True)
        
        # 尝试发送错误消息给用户，使用重试机制
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                if update.message:
                    await update.message.reply_text(
                        "处理您的邮箱时出现错误，请稍后再试或联系管理员。",
                        parse_mode=ParseMode.HTML
                    )
                break
            except Exception as send_error:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"无法发送错误消息到用户 {user_id}: {str(send_error)}")
                    break
                await asyncio.sleep(1)  # 等待1秒后重试
            
        return ConversationHandler.END

async def verify_email_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理/verify_email命令，验证邮箱
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    # 如果是直接带参数的命令，如 /verify_email 123456
    if context.args and len(context.args) > 0:
        verification_code = context.args[0]
        return await process_verification_code(update, context, verification_code)
    
    # 否则提示用户输入验证码
    await update.message.reply_text(
        TEMPLATES["email_verification_prompt"],
        parse_mode=ParseMode.HTML
    )
    return WAITING_FOR_VERIFICATION

async def verification_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理用户输入的验证码
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    try:
        # 添加详细日志，记录验证码接收
        user_id = update.effective_user.id
        logger.info(f"验证码处理函数被调用 - 用户ID: {user_id}")
        
        # 检查消息是否存在
        if not update.message:
            logger.error(f"用户 {user_id} 的更新对象中没有消息")
            return ConversationHandler.END
            
        message_text = update.message.text.strip()
        logger.info(f"收到用户 {user_id} 的验证码: '{message_text}'")
        
        # 处理取消命令
        if message_text.startswith('/cancel'):
            logger.info(f"用户 {user_id} 在输入验证码阶段取消操作")
            await update.message.reply_text(
                TEMPLATES.get("operation_cancelled", "操作已取消。"),
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 处理验证码
        verification_code = message_text
        return await process_verification_code(update, context, verification_code)
    except Exception as e:
        # 记录详细的错误信息
        user_id = update.effective_user.id if update.effective_user else "未知"
        logger.error(f"处理验证码输入时出错 - 用户ID: {user_id}, 错误: {str(e)}", exc_info=True)
        
        # 尝试发送错误消息给用户
        try:
            if update.message:
                await update.message.reply_text(
                    "处理您的验证码时出现错误，请稍后再试或联系管理员。",
                    parse_mode=ParseMode.HTML
                )
        except Exception as send_error:
            logger.error(f"无法发送错误消息到用户 {user_id}: {str(send_error)}")
            
        return ConversationHandler.END

async def process_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str) -> int:
    """
    @description: 处理验证码
    @param {Update} update: 更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    @param {str} code: 验证码
    @return {int}: 会话状态
    """
    user_id = update.effective_user.id
    logger.info(f"处理用户 {user_id} 的验证码: {code}")
    
    try:
        # 获取存储对象
        storage = context.application.bot_data.get("storage")
        if not storage:
            logger.error(f"存储对象未初始化，用户 {user_id} 的验证码处理失败")
            await update.message.reply_text("系统错误，请稍后重试或联系管理员")
            return ConversationHandler.END

        # 获取验证记录
        verifications = storage.get_email_verifications_by_user(user_id)
        if not verifications:
            logger.warning(f"用户 {user_id} 的验证记录不存在")
            await update.message.reply_text("验证码已过期，请重新发起验证")
            return ConversationHandler.END

        # 获取最新的验证记录
        verification = max(verifications, key=lambda v: v.created_at)
        logger.info(f"找到验证记录 - 验证码: {verification.verification_code}, 用户输入: {code}, 邮箱: {verification.email}")

        # 检查验证码是否正确
        if verification.verification_code != code:
            logger.warning(f"用户 {user_id} 输入的验证码不正确")
            await update.message.reply_text("验证码无效，请重新输入或使用 /cancel 命令取消操作")
            return WAITING_FOR_VERIFICATION

        # 检查验证码是否过期
        current_time = datetime.now()
        if verification.expires_at < current_time:
            logger.warning(f"用户 {user_id} 的验证码已过期")
            await update.message.reply_text("验证码已过期，请重新发起验证")
            return ConversationHandler.END

        # 获取用户记录
        user = storage.get_user(user_id)
        if not user:
            logger.error(f"用户 {user_id} 记录不存在")
            await update.message.reply_text("系统错误，请稍后重试或联系管理员")
            return ConversationHandler.END

        # 更新用户邮箱和验证状态
        try:
            user.email = verification.email
            user.email_verified = True
            user.last_email_change = datetime.now()
            verification.status = EmailVerifyStatus.VERIFIED
            storage.save_user(user)
            storage.add_email_verification(verification)

            logger.info(f"用户 {user_id} 成功验证邮箱: {user.email}")
            await update.message.reply_text(f"邮箱 {user.email} 验证成功！")
            
            # 清理会话数据
            if "pending_email" in context.user_data:
                del context.user_data["pending_email"]
                
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"更新用户数据时出错 - 用户ID: {user_id}, 错误: {str(e)}", exc_info=True)
            await update.message.reply_text("系统错误，请稍后重试或联系管理员")
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"处理用户 {user_id} 的验证码时发生错误: {str(e)}", exc_info=True)
        await update.message.reply_text("系统错误，请稍后重试或联系管理员")
        return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 取消当前操作
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    # 添加详细日志，记录取消命令接收
    user_id = update.effective_user.id
    logger.info(f"取消命令被调用 - 用户ID: {user_id}")
    logger.debug(f"更新对象内容: {update}")
    
    await update.message.reply_text(
        TEMPLATES["operation_cancelled"],
        parse_mode=ParseMode.HTML
    )
    
    logger.info(f"用户 {user_id} 成功取消当前操作")
    return ConversationHandler.END

async def change_email_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理更换邮箱的回调
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    query = update.callback_query
    await query.answer()
    
    # 发送新消息而不是编辑原消息，以便开始新的会话
    await query.message.reply_text(
        TEMPLATES["email_binding_prompt"],
        parse_mode=ParseMode.HTML
    )
    
    # 设置用户数据状态，标记用户正在更换邮箱
    context.user_data["changing_email"] = True
    
    return WAITING_FOR_EMAIL

async def keep_email_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理保持原邮箱的回调
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = storage.get_user(user_id)
    
    await query.edit_message_text(
        TEMPLATES["email_unchanged"].format(email=user.email),
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def start_email_binding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 开始邮箱绑定流程（从按钮回调调用）
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    # 检查是否是通过按钮回调调用
    if update.callback_query:
        query = update.callback_query
        user_id = query.from_user.id
        
        # 获取用户信息
        user = storage.get_user(user_id)
        if not user:
            user = User(
                user_id=user_id,
                username=query.from_user.username or "",
                join_date=datetime.now(),
                points=0
            )
            storage.save_user(user)
            
        # 再次获取最新数据
        user = storage.get_user(user_id)
        
        # 检查用户积分是否足够
        if user.points < MIN_POINTS_FOR_EMAIL_BINDING:
            await query.message.reply_text(
                TEMPLATES["email_binding_insufficient_points"].format(
                    required_points=MIN_POINTS_FOR_EMAIL_BINDING,
                    current_points=user.points
                ),
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 如果用户已经绑定了邮箱，询问是否要更换
        if user.email:
            keyboard = [
                [
                    InlineKeyboardButton("是，更换邮箱", callback_data="change_email"),
                    InlineKeyboardButton("否，保持不变", callback_data="keep_email")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                TEMPLATES["email_already_bound"].format(email=user.email),
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 提示用户输入邮箱
        await query.message.reply_text(
            TEMPLATES["email_binding_prompt"],
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_EMAIL
    else:
        # 正常命令调用
        return await bind_email_command(update, context)

async def debug_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 调试用 - 记录所有未被其他处理器处理的消息
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 保持当前会话状态
    """
    # 提取用户ID和消息内容
    user_id = update.effective_user.id if update.effective_user else "未知"
    
    if update.message:
        content_type = "文本消息" if update.message.text else "非文本消息"
        content = update.message.text if update.message.text else "无文本内容"
        logger.warning(f"调试: 收到未处理的{content_type} - 用户: {user_id}, 内容: '{content}'")
    elif update.callback_query:
        logger.warning(f"调试: 收到未处理的回调查询 - 用户: {user_id}, 数据: {update.callback_query.data}")
    else:
        logger.warning(f"调试: 收到未知类型的更新 - 用户: {user_id}, 更新类型: {type(update)}")
    
    # 不改变会话状态，返回END结束会话
    return ConversationHandler.END

def get_email_handlers() -> List:
    """
    @description: 获取邮箱相关的处理器
    @return {List}: 处理器列表
    """
    # 创建邮箱绑定会话处理器 - 采用全新配置方式
    email_binding_handler = ConversationHandler(
        entry_points=[
            CommandHandler("bind_email", bind_email_command),
            CommandHandler("bindemail", bind_email_command),
            CallbackQueryHandler(change_email_callback, pattern="^change_email$")
        ],
        states={
            # 在等待邮箱输入时，接受任何文本消息和取消命令
            WAITING_FOR_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, email_input),  # 任何非命令文本
                CommandHandler("cancel", cancel_command)
            ],
            # 在等待验证码输入时，接受任何文本消息和取消命令
            WAITING_FOR_VERIFICATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, verification_code_input),  # 任何非命令文本
                CommandHandler("cancel", cancel_command)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            # 添加通配符处理器用于调试
            MessageHandler(filters.ALL, debug_unknown_message)
        ],
        name="email_binding",
        conversation_timeout=300  # 5分钟超时
    )
    
    # 创建验证邮箱命令
    verify_email_handler = CommandHandler("verify_email", verify_email_command)
    
    # 创建保持当前邮箱回调
    keep_email_handler = CallbackQueryHandler(keep_email_callback, pattern="^keep_email$")
    
    return [
        email_binding_handler,
        verify_email_handler,
        keep_email_handler
    ] 