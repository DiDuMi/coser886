"""
@description: 处理账号权益恢复相关的功能
"""
import logging
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    CommandHandler, MessageHandler, filters, 
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from coser_bot.config.settings import (
    EMAIL_VERIFICATION_EXPIRY_MINUTES,
    RECOVERY_REQUEST_EXPIRY_DAYS,
    ADMIN_IDS
)
from coser_bot.config.constants import TEMPLATES, EmailVerifyStatus
from coser_bot.database.storage import Storage
from coser_bot.database.models import (
    User, EmailVerification, Group, UserGroupAccess, 
    RecoveryRequest, RecoveryStatus
)
from coser_bot.utils.email_sender import (
    generate_verification_code, send_verification_email, is_valid_email
)

logger = logging.getLogger(__name__)

# 创建Storage实例
storage = Storage()

# 会话状态
WAITING_FOR_EMAIL = 1
WAITING_FOR_VERIFICATION = 2
WAITING_FOR_REASON = 3

async def recover_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理/recover命令，开始账号权益恢复流程
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    # 检查用户是否已经有恢复请求
    existing_request = storage.get_pending_recovery_request_by_new_user(user_id)
    if existing_request:
        # 计算剩余有效期
        expiry_date = existing_request.created_at + timedelta(days=RECOVERY_REQUEST_EXPIRY_DAYS)
        days_left = (expiry_date - datetime.now()).days + 1
        
        await update.message.reply_text(
            TEMPLATES["recovery_request_exists"].format(
                request_id=existing_request.request_id,
                days_left=max(1, days_left)
            ),
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 提示用户先查看当前账号信息
    await update.message.reply_text(
        "在开始恢复流程之前，建议您先使用 /myinfo 命令查看当前账号信息，确认是否需要进行恢复操作。\n\n"
        "如果确认要继续恢复流程，请输入原账号绑定的邮箱地址。",
        parse_mode=ParseMode.HTML
    )
    
    return WAITING_FOR_EMAIL

async def recovery_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理用户输入的邮箱
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    email = update.message.text.strip().lower()
    
    # 记录用户输入的邮箱
    logger.info(f"用户 {update.effective_user.id} 输入邮箱: {email}")
    
    # 验证邮箱格式
    if not is_valid_email(email):
        await update.message.reply_text(
            TEMPLATES["email_format_invalid"],
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_EMAIL
    
    # 检查邮箱是否存在且已验证
    original_user = storage.get_user_by_email(email)
    if not original_user:
        logger.warning(f"用户 {update.effective_user.id} 输入的邮箱 {email} 未找到对应用户")
        await update.message.reply_text(
            TEMPLATES["recovery_email_not_found"],
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_EMAIL
    
    # 检查是否是当前用户
    if original_user.user_id == update.effective_user.id:
        logger.info(f"用户 {update.effective_user.id} 输入的邮箱绑定的就是当前账号")
        await update.message.reply_text(
            TEMPLATES["recovery_same_account"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 保存原始用户ID和邮箱到上下文
    context.user_data["original_user_id"] = original_user.user_id
    context.user_data["recovery_email"] = email
    logger.info(f"保存原始用户ID {original_user.user_id} 和邮箱 {email} 到上下文")
    
    # 生成验证码并发送邮件
    verification_code = generate_verification_code()
    user_id = update.effective_user.id
    
    # 保存验证信息到数据库
    verification = EmailVerification(
        user_id=user_id,
        email=email,
        verification_code=verification_code,
        status=EmailVerifyStatus.PENDING
    )
    
    success = storage.add_email_verification(verification)
    if not success:
        logger.error(f"为用户 {user_id} 添加邮箱验证记录失败")
        await update.message.reply_text(
            TEMPLATES["verification_save_failed"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 发送验证邮件
    subject = "Coser Community Account Recovery Verification"
    message = f"Your verification code is: {verification_code}\n\nThis code will expire in {EMAIL_VERIFICATION_EXPIRY_MINUTES} minutes."
    
    success, message = await send_verification_email(email, subject, message)
    if not success:
        logger.error(f"向邮箱 {email} 发送验证邮件失败: {message}")
        await update.message.reply_text(
            TEMPLATES["email_send_failed"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    logger.info(f"向邮箱 {email} 发送验证邮件成功")
    await update.message.reply_text(
        TEMPLATES["recovery_verification_sent"].format(
            email=email,
            expiry_minutes=EMAIL_VERIFICATION_EXPIRY_MINUTES
        ),
        parse_mode=ParseMode.HTML
    )
    return WAITING_FOR_VERIFICATION

async def recovery_verification_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理用户输入的验证码
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    verification_code = update.message.text.strip()
    return await process_recovery_verification(update, context, verification_code)

async def process_recovery_verification(update: Update, context: ContextTypes.DEFAULT_TYPE, verification_code: str) -> int:
    """
    @description: 处理恢复流程中的验证码验证
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @param {str} verification_code: 用户输入的验证码
    @return {int}: 会话状态
    """
    global storage
    
    new_user_id = update.effective_user.id
    
    # 检查新账号是否已经有群组权限
    new_user_groups = storage.get_user_group_accesses(new_user_id)
    if new_user_groups:
        await update.message.reply_text(
            "您的当前账号已经拥有群组权限，无法进行恢复操作。如有问题请联系管理员。",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 获取邮箱
    recovery_email = context.user_data.get("recovery_email")
    if not recovery_email:
        logger.warning(f"用户 {new_user_id} 的会话数据丢失(邮箱)")
        await update.message.reply_text(
            TEMPLATES["recovery_session_expired"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 验证验证码
    verification = storage.get_email_verification_by_code(verification_code)
    if not verification or verification.email != recovery_email:
        logger.warning(f"用户 {new_user_id} 输入的验证码无效: {verification_code}")
        await update.message.reply_text(
            TEMPLATES["verification_code_invalid"],
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_VERIFICATION
    
    # 检查验证码是否过期
    if verification.status == EmailVerifyStatus.EXPIRED or verification.expires_at < datetime.now():
        logger.warning(f"用户 {new_user_id} 输入的验证码已过期")
        verification.status = EmailVerifyStatus.EXPIRED
        storage.update_email_verification(verification)
        await update.message.reply_text(
            TEMPLATES["verification_code_expired"],
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_VERIFICATION
    
    # 验证成功，获取原始用户信息
    original_user = storage.get_user_by_email(recovery_email)
    if not original_user:
        logger.error(f"无法找到邮箱 {recovery_email} 对应的用户")
        await update.message.reply_text(
            TEMPLATES["recovery_email_not_found"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 检查原账号是否已被其他账号恢复
    existing_recoveries = [r for r in storage.recovery_requests if 
                         r.old_user_id == original_user.user_id and 
                         r.status == RecoveryStatus.APPROVED]
    if existing_recoveries:
        await update.message.reply_text(
            "该账号已被其他用户恢复，如有疑问请联系管理员。",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 检查是否存在重复恢复请求
    pending_requests = [r for r in storage.recovery_requests if 
                       r.new_user_id == new_user_id and 
                       r.status == RecoveryStatus.PENDING]
    if pending_requests:
        await update.message.reply_text(
            f"您已有正在处理的恢复请求（请求ID: {pending_requests[0].request_id}），"
            f"请等待管理员审核或联系管理员了解进度。",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 保存原始用户ID到上下文
    original_user_id = original_user.user_id
    context.user_data["original_user_id"] = original_user_id
    logger.info(f"用户 {new_user_id} 验证成功，保存原始用户ID {original_user_id} 到上下文")
    
    # 更新验证状态
    verification.status = EmailVerifyStatus.VERIFIED
    storage.update_email_verification(verification)
    
    # 强制重新加载数据
    storage = Storage()
    storage._load_data()
    
    # 获取原始用户的群组访问权限
    original_user_groups = storage.get_user_group_accesses(original_user_id)
    logger.info(f"原始用户 {original_user_id} ({original_user.username}) 的群组访问权限: {len(original_user_groups)} 个")
    
    # 构建群组信息文本
    group_info = []
    for access in original_user_groups:
        group = storage.get_group(access.group_id)
        if not group:
            logger.warning(f"找不到群组ID {access.group_id} 的信息")
            continue
            
        # 确定访问类型和有效期
        access_type = "付费" if group.is_paid else "免费"
        if access.end_date:
            expiry = f"有效期至 {access.end_date.strftime('%Y-%m-%d')}"
        else:
            expiry = "永久"
            
        group_info.append(f"  {len(group_info) + 1}. {group.group_name} ({access_type}，{expiry})")
        logger.info(f"添加群组信息: {group.group_name} ({access_type}，{expiry})")
    
    group_info_text = "\n".join(group_info) if group_info else "  无群组权益"
    
    # 显示原账号信息
    account_info = TEMPLATES["recovery_account_info"].format(
        username=original_user.username,
        join_date=original_user.join_date.strftime("%Y-%m-%d"),
        points=original_user.points,
        group_info=group_info_text
    )
    
    # 添加恢复说明
    recovery_info = (
        "\n\n<b>恢复说明：</b>\n"
        "1. 恢复后，原账号的群组权限将转移到新账号\n"
        "2. 积分和其他权益也将一并转移\n"
        "3. 恢复操作不可逆，请确认信息无误\n"
        "4. 如有疑问，可以取消操作并联系管理员\n\n"
        "请确认是否继续恢复操作？"
    )
    
    await update.message.reply_text(
        account_info + recovery_info,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("申请恢复权益", callback_data="request_recovery")],
            [InlineKeyboardButton("取消", callback_data="cancel_recovery")]
        ])
    )
    
    # 设置会话状态为等待原因输入
    context.user_data["waiting_for_recovery"] = True
    
    return WAITING_FOR_REASON

async def request_recovery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理申请恢复权益的回调
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    query = update.callback_query
    await query.answer()
    
    # 确保上下文数据存在
    if "original_user_id" not in context.user_data or "recovery_email" not in context.user_data:
        logger.warning(f"用户 {update.effective_user.id} 的会话数据丢失")
        await query.edit_message_text(
            TEMPLATES["recovery_session_expired"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    logger.info(f"用户 {update.effective_user.id} 点击了申请恢复权益按钮，上下文数据: {context.user_data}")
    
    # 提示用户填写申请原因
    await query.edit_message_text(
        TEMPLATES["recovery_reason_prompt"],
        parse_mode=ParseMode.HTML
    )
    
    # 重要：将会话状态保存到用户数据中，以便在下一步中使用
    context.user_data["waiting_for_reason"] = True
    
    return WAITING_FOR_REASON

async def recovery_reason_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 处理用户输入的申请原因
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    reason = update.message.text.strip()
    
    logger.info(f"收到用户 {update.effective_user.id} 的恢复原因: {reason}")
    logger.info(f"当前上下文数据: {context.user_data}")
    
    # 检查是否在等待恢复原因状态
    if not context.user_data.get("waiting_for_reason") and not context.user_data.get("waiting_for_recovery"):
        logger.warning(f"用户 {update.effective_user.id} 不在等待恢复原因状态")
        await update.message.reply_text(
            "请先完成验证流程，然后再提交恢复原因。",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 检查原因长度
    if len(reason) > 50:
        logger.info(f"用户 {update.effective_user.id} 的恢复原因过长: {len(reason)} 字符")
        await update.message.reply_text(
            TEMPLATES["recovery_reason_too_long"],
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_REASON
    
    # 获取原始用户ID和邮箱
    original_user_id = context.user_data.get("original_user_id")
    recovery_email = context.user_data.get("recovery_email")
    
    logger.info(f"从上下文获取数据: original_user_id={original_user_id}, recovery_email={recovery_email}")
    
    if not original_user_id or not recovery_email:
        logger.warning(f"用户 {update.effective_user.id} 的会话数据丢失")
        await update.message.reply_text(
            TEMPLATES["recovery_session_expired"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # 确保用户信息存在
    new_user_id = update.effective_user.id
    new_username = update.effective_user.username
    await save_user_if_not_exists(new_user_id, new_username)
    
    # 生成请求ID
    import random
    import string
    request_id = 'RA' + ''.join(random.choices(string.digits, k=5))
    
    logger.info(f"为用户 {new_user_id} 创建恢复请求 {request_id}")
    
    recovery_request = RecoveryRequest(
        request_id=request_id,
        old_user_id=original_user_id,
        new_user_id=new_user_id,
        email=recovery_email,
        reason=reason,
        status=RecoveryStatus.PENDING,
        created_at=datetime.now()
    )
    
    try:
        success = storage.add_recovery_request(recovery_request)
        logger.info(f"添加恢复请求结果: {success}")
        
        if not success:
            logger.error(f"为用户 {new_user_id} 添加恢复请求失败")
            await update.message.reply_text(
                TEMPLATES["recovery_request_failed"],
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
        
        # 通知用户申请已提交
        logger.info(f"向用户 {new_user_id} 发送申请提交成功通知")
        await update.message.reply_text(
            TEMPLATES["recovery_request_submitted"].format(
                request_id=request_id
            ),
            parse_mode=ParseMode.HTML
        )
        
        # 通知管理员
        logger.info(f"准备通知管理员关于恢复请求 {request_id}")
        await notify_admins_about_recovery(context, recovery_request)
        
        # 清除会话状态
        context.user_data.pop("waiting_for_reason", None)
        context.user_data.pop("waiting_for_recovery", None)
        
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"处理恢复请求时发生错误: {e}")
        await update.message.reply_text(
            TEMPLATES["recovery_request_failed"],
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

async def notify_admins_about_recovery(context: ContextTypes.DEFAULT_TYPE, recovery_request: RecoveryRequest):
    """
    @description: 通知管理员有新的恢复请求并处理恢复流程
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @param {RecoveryRequest} recovery_request: 恢复请求对象
    """
    global storage
    
    try:
        logger.info(f"开始执行恢复流程 - 请求ID: {recovery_request.request_id}, 状态: {recovery_request.status}, 类型: {recovery_request.approval_type}")
        
        # 获取原始用户和新用户信息
        original_user = storage.get_user(recovery_request.old_user_id)
        new_user = storage.get_user(recovery_request.new_user_id)
        
        if not original_user or not new_user:
            logger.error(f"无法获取用户信息: 原用户ID {recovery_request.old_user_id}, 新用户ID {recovery_request.new_user_id}")
            return
            
        logger.debug(f"用户信息 - 原用户: {original_user.username} ({original_user.user_id}), 新用户: {new_user.username} ({new_user.user_id})")
        
        # 重新加载数据
        storage._load_data()
        
        # 获取原始用户的群组访问权限
        original_user_groups = storage.get_user_group_accesses(recovery_request.old_user_id)
        logger.info(f"原始用户 {recovery_request.old_user_id} ({original_user.username}) 的群组访问权限: {len(original_user_groups)} 个")
        
        # 发送恢复开始通知
        recovery_type_text = {
            "full": "完全",
            "partial": "部分",
            "points_only": "仅积分"
        }.get(recovery_request.approval_type, "完全")
        
        start_message = (
            f"🔄 <b>开始处理恢复请求</b>\n"
            f"请求ID: {recovery_request.request_id}\n"
            f"处理类型: {recovery_type_text}恢复\n"
            f"请耐心等待处理完成..."
        )
        
        await context.bot.send_message(
            chat_id=recovery_request.new_user_id,
            text=start_message,
            parse_mode=ParseMode.HTML
        )
        
        # 处理积分恢复
        points_message = ""
        if recovery_request.approval_type in ["full", "points_only"]:
            try:
                new_user.points = original_user.points
                if storage.save_user(new_user):
                    points_message = f"✅ 积分恢复成功: {original_user.points} 分\n"
                    logger.info(f"成功将 {original_user.points} 积分从用户 {recovery_request.old_user_id} 转移到用户 {recovery_request.new_user_id}")
                else:
                    points_message = f"❌ 积分恢复失败\n"
                    logger.error(f"保存用户积分失败: {new_user.user_id}")
            except Exception as e:
                points_message = f"❌ 积分恢复出错: {str(e)}\n"
                logger.error(f"恢复积分时出错: {str(e)}")
        
        # 如果是仅恢复积分，直接发送结果
        if recovery_request.approval_type == "points_only":
            result_message = (
                f"🔄 <b>恢复请求处理完成</b>\n"
                f"请求ID: {recovery_request.request_id}\n\n"
                f"{points_message}\n"
                f"如有问题请联系管理员。"
            )
            
            await context.bot.send_message(
                chat_id=recovery_request.new_user_id,
                text=result_message,
                parse_mode=ParseMode.HTML
            )
            return
        
        # 处理群组恢复
        if recovery_request.approval_type in ["full", "partial"]:
            # 获取要恢复的群组
            groups_to_restore = []
            invalid_groups = []
            
            selected_groups = context.user_data.get('selected_groups', [])
            
            for access in original_user_groups:
                group = storage.get_group(access.group_id)
                if not group:
                    logger.warning(f"找不到群组ID {access.group_id} 的信息")
                    continue
                
                # 如果是部分恢复，只处理选中的群组
                if recovery_request.approval_type == "partial" and group.group_id not in selected_groups:
                    continue
                
                try:
                    # 检查群组是否存在且机器人是管理员
                    chat = await context.bot.get_chat(group.group_id)
                    bot_member = await chat.get_member(context.bot.id)
                    
                    if bot_member.status in ['administrator', 'creator']:
                        groups_to_restore.append(group)
                        logger.info(f"验证通过: 群组 {group.group_name} ({group.group_id})")
                    else:
                        invalid_groups.append((group, "机器人不是管理员"))
                        logger.warning(f"机器人在群组 {group.group_name} ({group.group_id}) 中不是管理员")
                except Exception as e:
                    invalid_groups.append((group, str(e)))
                    logger.error(f"验证群组 {group.group_name} ({group.group_id}) 失败: {str(e)}")
            
            # 生成邀请链接
            logger.info(f"开始为 {len(groups_to_restore)} 个群组生成邀请链接")
            invite_links = await generate_invite_links(context.bot, recovery_request.new_user_id, groups_to_restore)
            
            # 复制群组访问权限
            success_groups = []
            failed_groups = []
            
            for group in groups_to_restore:
                try:
                    # 查找原始访问权限
                    original_access = next((a for a in original_user_groups if a.group_id == group.group_id), None)
                    if not original_access:
                        continue
                    
                    # 创建新的访问权限
                    new_access = UserGroupAccess(
                        user_id=recovery_request.new_user_id,
                        group_id=group.group_id,
                        start_date=datetime.now(),
                        end_date=original_access.end_date
                    )
                    
                    if storage.add_user_group_access(new_access):
                        success_groups.append(group)
                        logger.info(f"成功复制群组 {group.group_id} 的访问权限给用户 {recovery_request.new_user_id}")
                    else:
                        failed_groups.append((group, "保存访问权限失败"))
                        logger.error(f"保存群组 {group.group_id} 的访问权限失败")
                except Exception as e:
                    failed_groups.append((group, str(e)))
                    logger.error(f"处理群组 {group.group_id} 的访问权限时出错: {str(e)}")
            
            # 构建结果消息
            result_message = (
                f"🔄 <b>恢复请求处理完成</b>\n"
                f"请求ID: {recovery_request.request_id}\n\n"
                f"{points_message}\n"
                f"群组恢复结果：\n"
                f"✅ 成功恢复: {len(success_groups)} 个群组\n"
            )
            
            if success_groups:
                result_message += "\n<b>群组邀请链接（24小时内有效）：</b>\n"
                for group in success_groups:
                    if group.group_id in invite_links:
                        result_message += f"• {group.group_name}: {invite_links[group.group_id]}\n"
            
            if invalid_groups or failed_groups:
                result_message += "\n<b>未能恢复的群组：</b>\n"
                for group, reason in invalid_groups + failed_groups:
                    result_message += f"• {group.group_name}: {reason}\n"
            
            result_message += "\n请在24小时内使用这些邀请链接加入群组。如有问题请联系管理员。"
            
            # 发送结果消息给用户
            await context.bot.send_message(
                chat_id=recovery_request.new_user_id,
                text=result_message,
                parse_mode=ParseMode.HTML
            )
            
            # 更新管理员消息
            admin_message = (
                f"✅ <b>恢复请求处理完成</b>\n"
                f"请求ID: {recovery_request.request_id}\n"
                f"新用户: {new_user.username} (ID: {new_user.user_id})\n"
                f"原用户: {original_user.username} (ID: {original_user.user_id})\n\n"
                f"处理结果:\n"
                f"• 积分: {points_message}\n"
                f"• 成功恢复群组: {len(success_groups)} 个\n"
                f"• 生成邀请链接: {len(invite_links)} 个\n"
                f"• 失败群组: {len(invalid_groups) + len(failed_groups)} 个"
            )
            
            # 通知所有管理员
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"无法发送通知给管理员 {admin_id}: {str(e)}")
    
    except Exception as e:
        error_message = f"❌ 处理恢复请求时出错: {str(e)}\n请联系管理员处理。"
        logger.error(f"处理恢复请求时出错: {str(e)}")
        
        try:
            await context.bot.send_message(
                chat_id=recovery_request.new_user_id,
                text=error_message,
                parse_mode=ParseMode.HTML
            )
        except:
            logger.error("无法发送错误通知给用户")

async def generate_invite_links(bot: Bot, user_id: int, groups: List[Group]) -> Dict[int, str]:
    """
    生成群组邀请链接
    @param bot: Bot实例
    @param user_id: 用户ID
    @param groups: 需要生成邀请链接的群组列表
    @return: 群组ID到邀请链接的映射字典
    """
    invite_links = {}
    storage_instance = Storage()
    
    if not groups:
        logger.warning(f"没有需要生成邀请链接的群组")
        return invite_links
        
    logger.info(f"开始为用户 {user_id} 生成 {len(groups)} 个群组的邀请链接")
    
    for group in groups:
        try:
            logger.info(f"正在为群组 {group.group_id} ({group.group_name}) 生成邀请链接")
            
            # 生成24小时有效的邀请链接
            expires_at = datetime.now() + timedelta(hours=24)
            try:
                # 检查机器人是否在群组中且是管理员
                try:
                    chat_member = await bot.get_chat_member(chat_id=group.group_id, user_id=bot.id)
                    if not chat_member.status in ['administrator', 'creator']:
                        logger.error(f"机器人在群组 {group.group_id} 中不是管理员")
                        continue
                except Exception as e:
                    logger.error(f"检查机器人权限失败: {str(e)}")
                    continue
                
                invite_link = await bot.create_chat_invite_link(
                    chat_id=group.group_id,
                    expire_date=expires_at,
                    member_limit=1  # 限制只能使用一次
                )
                logger.info(f"成功生成群组 {group.group_id} 的邀请链接")
                
                # 保存邀请链接
                if storage_instance.add_invite_link(
                    group_id=group.group_id,
                    user_id=user_id,
                    invite_link=invite_link.invite_link,
                    expires_at=expires_at
                ):
                    invite_links[group.group_id] = invite_link.invite_link
                    logger.info(f"已保存群组 {group.group_id} 的邀请链接到数据库")
                else:
                    logger.error(f"保存群组 {group.group_id} 的邀请链接失败")
                    continue
                    
            except Exception as e:
                logger.error(f"生成群组 {group.group_id} 的邀请链接失败: {str(e)}")
                continue
                
        except Exception as e:
            logger.error(f"处理群组 {group.group_id} 时出错: {str(e)}")
            continue
    
    logger.info(f"完成邀请链接生成，共生成 {len(invite_links)} 个链接")
    return invite_links

async def approve_recovery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理批准恢复请求的回调
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    """
    query = update.callback_query
    await query.answer()
    
    # 获取请求ID和审核类型
    data = query.data
    logger.info(f"收到恢复请求回调数据: {data}")
    
    try:
        # 解析回调数据
        parts = data.split("_")
        action = parts[0]  # approve 或 confirm
        
        # 改进回调数据解析逻辑
        if action == "approve":
            request_id = parts[2] if len(parts) > 2 else ""
            approval_type = parts[3] if len(parts) > 3 else "full"
        elif action == "confirm":
            request_id = parts[2] if len(parts) > 2 else ""
            approval_type = parts[3] if len(parts) > 3 else "full"
        else:
            logger.warning(f"未知的操作类型: {action}")
            await query.edit_message_text(
                text="❌ 未知的操作类型",
                parse_mode=ParseMode.HTML
            )
            return
        
        logger.info(f"解析回调数据 - 动作: {action}, 请求ID: {request_id}, 恢复类型: {approval_type}")
        
        # 获取恢复请求
        recovery_request = storage.get_recovery_request(request_id)
        if not recovery_request:
            logger.warning(f"恢复请求不存在: {request_id}")
            await query.edit_message_text(
                text="❌ 该恢复请求已不存在",
                parse_mode=ParseMode.HTML
            )
            return
            
        if recovery_request.status != RecoveryStatus.PENDING:
            logger.warning(f"恢复请求状态不是待处理: {request_id}, 当前状态: {recovery_request.status}")
            await query.edit_message_text(
                text="❌ 该恢复请求已被处理",
                parse_mode=ParseMode.HTML
            )
            return
            
        # 获取用户信息
        original_user = storage.get_user(recovery_request.old_user_id)
        new_user = storage.get_user(recovery_request.new_user_id)
        
        if not original_user or not new_user:
            logger.error(f"无法找到用户信息 - 原用户: {recovery_request.old_user_id}, 新用户: {recovery_request.new_user_id}")
            await query.edit_message_text(
                text="❌ 无法找到相关用户信息",
                parse_mode=ParseMode.HTML
            )
            return
            
        # 如果是确认操作
        if action == "confirm":
            logger.info(f"执行确认操作 - 请求ID: {request_id}, 恢复类型: {approval_type}")
            logger.debug(f"确认恢复操作前 - 请求状态: {recovery_request.status}, 管理员: {update.effective_user.username}")
            
            # 确保请求状态正确
            if recovery_request.status != RecoveryStatus.PENDING:
                logger.warning(f"恢复请求状态不正确，当前状态: {recovery_request.status}")
                await query.edit_message_text(
                    text=f"❌ 该恢复请求当前状态为: {recovery_request.status.value}，无法处理",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # 更新请求状态
            recovery_request.status = RecoveryStatus.APPROVED
            recovery_request.admin_id = update.effective_user.id
            recovery_request.process_time = datetime.now()
            recovery_request.approval_type = approval_type
            recovery_request.admin_note = f"由管理员 {update.effective_user.username} 批准 - {approval_type} 恢复"
            
            logger.debug(f"更新请求状态 - 新状态: {recovery_request.status}, 审批类型: {approval_type}")
            
            if not storage.update_recovery_request(recovery_request):
                logger.error(f"更新恢复请求状态失败 - 请求ID: {request_id}")
                await query.edit_message_text(
                    text="❌ 更新恢复请求状态失败",
                    parse_mode=ParseMode.HTML
                )
                return
            
            logger.debug(f"准备通知管理员并处理恢复流程 - 请求ID: {request_id}")
            
            try:
                # 通知用户并处理恢复流程
                await notify_admins_about_recovery(context, recovery_request)
                
                logger.debug(f"恢复流程处理完成 - 请求ID: {request_id}")
                
                # 更新管理员消息
                await query.edit_message_text(
                    text=f"✅ 恢复请求 {recovery_request.request_id} 已被管理员 {update.effective_user.username} 批准 ({approval_type} 恢复)",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"处理恢复请求时发生错误: {e}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                
                await query.edit_message_text(
                    text=f"❌ 处理恢复请求时发生错误: {str(e)[:100]}",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # 记录日志
            logger.info(f"管理员 {update.effective_user.id} 批准了用户 {recovery_request.new_user_id} 的恢复请求 {request_id} ({approval_type} 恢复)")
            return
            
        # 根据恢复类型显示不同的确认界面
        if approval_type == "full":
            # 显示完全恢复确认界面
            keyboard = [
                [
                    InlineKeyboardButton("确认完全恢复", callback_data=f"confirm_recovery_{request_id}_full"),
                    InlineKeyboardButton("部分恢复", callback_data=f"approve_recovery_{request_id}_partial")
                ],
                [
                    InlineKeyboardButton("仅恢复积分", callback_data=f"approve_recovery_{request_id}_points_only"),
                    InlineKeyboardButton("返回", callback_data=f"admin_menu")
                ]
            ]
            
            message = (
                f"🔄 <b>完全恢复确认</b>\n"
                f"请求ID: {request_id}\n\n"
                f"原账号: {original_user.username} (ID: {original_user.user_id})\n"
                f"新账号: {new_user.username} (ID: {new_user.user_id})\n\n"
                f"请选择恢复类型："
            )
            
            await query.edit_message_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        elif approval_type == "partial":
            # 显示群组选择界面
            groups = []
            for access in storage.get_user_group_accesses(original_user.user_id):
                group = storage.get_group(access.group_id)
                if group:
                    groups.append((group, access))
            
            keyboard = []
            for group, access in groups:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{'✅' if group.group_id in context.user_data.get('selected_groups', []) else '❌'} {group.group_name}",
                        callback_data=f"toggle_group_{request_id}_{group.group_id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("确认选择", callback_data=f"confirm_recovery_{request_id}_partial"),
                InlineKeyboardButton("返回", callback_data=f"approve_recovery_{request_id}_full")
            ])
            
            message = (
                f"🔄 <b>部分恢复 - 选择要恢复的群组</b>\n"
                f"请求ID: {request_id}\n\n"
                f"点击群组名称以选择/取消选择："
            )
            
            await query.edit_message_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        elif approval_type == "points_only":
            # 确认仅恢复积分
            keyboard = [
                [
                    InlineKeyboardButton("确认仅恢复积分", callback_data=f"confirm_recovery_{request_id}_points_only"),
                    InlineKeyboardButton("返回", callback_data=f"approve_recovery_{request_id}_full")
                ]
            ]
            
            message = (
                f"💰 <b>仅恢复积分确认</b>\n"
                f"请求ID: {request_id}\n"
                f"将恢复积分: {original_user.points} 分\n\n"
                f"确认仅恢复积分吗？"
            )
            
            await query.edit_message_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

    except Exception as e:
        logger.error(f"处理恢复请求回调时发生错误: {e}")
        await query.edit_message_text(
            text="❌ 处理恢复请求回调时发生错误",
            parse_mode=ParseMode.HTML
        )

async def reject_recovery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理拒绝恢复请求的回调
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    """
    query = update.callback_query
    await query.answer()
    
    # 获取请求ID
    request_id = query.data.replace("reject_recovery_", "")
    
    # 获取恢复请求
    recovery_request = storage.get_recovery_request(request_id)
    if not recovery_request:
        await query.edit_message_text(
            text="❌ 该恢复请求已不存在",
            parse_mode=ParseMode.HTML
        )
        return
        
    if recovery_request.status != RecoveryStatus.PENDING:
        await query.edit_message_text(
            text="❌ 该恢复请求已被处理",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 更新请求状态
    recovery_request.status = RecoveryStatus.REJECTED
    recovery_request.admin_id = update.effective_user.id
    recovery_request.process_time = datetime.now()
    
    if not storage.update_recovery_request(recovery_request):
        await query.edit_message_text(
            text="❌ 更新恢复请求状态失败",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 通知用户恢复请求已拒绝
    try:
        await context.bot.send_message(
            chat_id=recovery_request.new_user_id,
            text=TEMPLATES["recovery_rejected"],
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"无法发送恢复拒绝通知给用户 {recovery_request.new_user_id}: {e}")
    
    # 更新管理员消息
    await query.edit_message_text(
        text=f"❌ 恢复请求 {recovery_request.request_id} 已被管理员 {update.effective_user.username or update.effective_user.id} 拒绝",
        parse_mode=ParseMode.HTML
    )
    
    # 记录日志
    logger.info(f"管理员 {update.effective_user.id} 拒绝了用户 {recovery_request.new_user_id} 的恢复请求 {request_id}")

async def request_more_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理请求补充信息的回调"""
    query = update.callback_query
    await query.answer()
    
    # 获取请求ID
    request_id = query.data.replace("request_more_info_", "")
    
    # 获取恢复请求
    recovery_request = storage.get_recovery_request(request_id)
    if not recovery_request:
        await query.edit_message_text(
            text="❌ 该恢复请求已不存在",
            parse_mode=ParseMode.HTML
        )
        return
        
    if recovery_request.status != RecoveryStatus.PENDING:
        await query.edit_message_text(
            text="❌ 该恢复请求已被处理",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 更新请求状态
    recovery_request.status = RecoveryStatus.INFO_NEEDED
    recovery_request.admin_id = update.effective_user.id
    recovery_request.process_time = datetime.now()
    
    if not storage.update_recovery_request(recovery_request):
        await query.edit_message_text(
            text="❌ 更新恢复请求状态失败",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 提示管理员输入需要补充的信息
    await query.edit_message_text(
        text=f"请输入需要用户补充的信息（请以 /ask_{request_id} 开头）：\n"
             f"例如：/ask_{request_id} 请提供您之前使用的用户名",
        parse_mode=ParseMode.HTML
    )
    
    # 记录日志
    logger.info(f"管理员 {update.effective_user.id} 请求用户 {recovery_request.new_user_id} 补充恢复请求 {request_id} 的信息")

async def ask_more_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理管理员发送补充信息请求的命令"""
    message = update.message
    command_parts = message.text.split(" ", 1)
    
    if len(command_parts) < 2:
        await message.reply_text(
            text="请输入需要用户补充的具体信息",
            parse_mode=ParseMode.HTML
        )
        return
        
    # 解析请求ID和补充信息
    command = command_parts[0]  # /ask_RA12345
    request_id = command.replace("/ask_", "")
    info_needed = command_parts[1]
    
    # 获取恢复请求
    recovery_request = storage.get_recovery_request(request_id)
    if not recovery_request:
        await message.reply_text(
            text="❌ 该恢复请求已不存在",
            parse_mode=ParseMode.HTML
        )
        return
        
    if recovery_request.status != RecoveryStatus.INFO_NEEDED:
        await message.reply_text(
            text="❌ 该恢复请求状态不正确",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        # 发送补充信息请求给用户
        await context.bot.send_message(
            chat_id=recovery_request.new_user_id,
            text=f"管理员请求您补充以下信息：\n\n{info_needed}\n\n"
                 f"请直接回复此消息提供补充信息。",
            parse_mode=ParseMode.HTML
        )
        
        # 通知管理员
        await message.reply_text(
            text="✅ 已将补充信息请求发送给用户",
            parse_mode=ParseMode.HTML
        )
        
        # 记录日志
        logger.info(f"管理员 {update.effective_user.id} 向用户 {recovery_request.new_user_id} 发送了恢复请求 {request_id} 的补充信息请求")
        
    except Exception as e:
        logger.error(f"发送补充信息请求失败: {str(e)}")
        await message.reply_text(
            text="❌ 发送补充信息请求失败",
            parse_mode=ParseMode.HTML
        )

async def list_recovery_requests_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理查看恢复请求列表的命令"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            text="❌ 只有管理员可以使用此命令",
            parse_mode=ParseMode.HTML
        )
        return

    # 获取所有待处理的恢复请求
    all_requests = storage.recovery_requests
    pending_requests = [r for r in all_requests if r.status == RecoveryStatus.PENDING]
    
    if not pending_requests:
        await update.message.reply_text(
            text="📝 当前没有待处理的恢复请求",
            parse_mode=ParseMode.HTML
        )
        return
    
    # 构建请求列表消息
    message = "📋 待处理的恢复请求列表：\n\n"
    for req in pending_requests:
        # 获取用户信息
        old_user = storage.get_user(req.old_user_id)
        new_user = storage.get_user(req.new_user_id)
        
        old_username = old_user.username if old_user else f"用户{req.old_user_id}"
        new_username = new_user.username if new_user else f"用户{req.new_user_id}"
        
        message += (
            f"请求ID: {req.request_id}\n"
            f"原账号: {old_username} ({req.old_user_id})\n"
            f"新账号: {new_username} ({req.new_user_id})\n"
            f"邮箱: {req.email}\n"
            f"原因: {req.reason}\n"
            f"申请时间: {req.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        
        # 添加操作按钮
        keyboard = [
            [
                InlineKeyboardButton("批准", callback_data=f"approve_recovery_{req.request_id}"),
                InlineKeyboardButton("拒绝", callback_data=f"reject_recovery_{req.request_id}")
            ],
            [
                InlineKeyboardButton("要求补充信息", callback_data=f"request_more_info_{req.request_id}")
            ]
        ]
        
        await update.message.reply_text(
            text=message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        message = ""  # 清空消息，为下一个请求准备

async def save_user_if_not_exists(user_id: int, username: str = None) -> None:
    """如果用户不存在，则保存用户信息"""
    if not storage.get_user(user_id):
        user = User(
            user_id=user_id,
            username=username or f"user_{user_id}",
            join_date=datetime.now(),
            points=0,
            streak_days=0
        )
        storage.save_user(user)
        logger.info(f"创建新用户: {user_id}")

def get_recovery_handlers() -> List:
    """
    @description: 获取账号恢复相关的处理器
    @return {List}: 处理器列表
    """
    # 创建账号恢复会话处理器
    recovery_handler = ConversationHandler(
        entry_points=[
            CommandHandler("recover", recover_command),
            CommandHandler("recovery", recover_command)
        ],
        states={
            WAITING_FOR_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, recovery_email_input)],
            WAITING_FOR_VERIFICATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, recovery_verification_input)],
            WAITING_FOR_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recovery_reason_input),
                CallbackQueryHandler(request_recovery_callback, pattern="^request_recovery$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="recovery_conversation",
        persistent=False,
        allow_reentry=True
    )
    
    # 创建回调查询处理器
    callback_handlers = [
        CallbackQueryHandler(approve_recovery_callback, pattern="^approve_recovery_"),
        CallbackQueryHandler(approve_recovery_callback, pattern="^confirm_recovery_"),
        CallbackQueryHandler(reject_recovery_callback, pattern="^reject_recovery_"),
        CallbackQueryHandler(request_more_info_callback, pattern="^request_more_info_")
    ]
    
    # 添加补充信息命令处理器
    command_handlers = [
        MessageHandler(
            filters.COMMAND & filters.Regex(r"^/ask_RA\d+"),
            ask_more_info_command
        ),
        CommandHandler("list_recovery", list_recovery_requests_command)
    ]
    
    return [recovery_handler] + callback_handlers + command_handlers

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    @description: 取消当前操作
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 回调上下文
    @return {int}: 会话状态
    """
    await update.message.reply_text(
        TEMPLATES["operation_cancelled"],
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END 