"""
@description: 群组同步模块，负责同步用户的群组权益数据
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from telegram import Update
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters
)

from ..database.storage import Storage
from ..database.models import UserGroupAccess, Group

logger = logging.getLogger(__name__)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理用户消息，记录用户所在的群组"""
    if not update.effective_chat or not update.effective_user:
        return
        
    chat = update.effective_chat
    user = update.effective_user
    
    # 只处理群组消息
    if not chat.type.endswith("group") and not chat.type == "channel":
        return
        
    storage = Storage()
    
    # 检查当前群组是否是已知的权益群组
    current_group = storage.get_group_by_chat_id(chat.id)
    if not current_group:
        # 如果不是已知的权益群组，直接返回
        return
        
    logger.info(f"处理用户 {user.username or user.first_name} (ID: {user.id}) 在权益群组 {chat.title} (ID: {chat.id}) 的消息")
    
    # 首先处理当前群组的权限
    try:
        # 获取用户在当前群组的访问记录
        current_access = storage.get_user_group_access(user.id, current_group.group_id)
        if not current_access:
            # 如果用户在当前群组中没有访问记录，创建一个
            current_access = UserGroupAccess(
                access_id=len(storage.user_group_access) + 1,
                user_id=user.id,
                group_id=current_group.group_id,
                start_date=datetime.now(),
                end_date=None
            )
            storage.add_user_group_access(current_access)
            logger.info(f"用户 {user.username or user.first_name} (ID: {user.id}) 加入权益群组 {current_group.group_name}")
            storage._save_data()
    except Exception as e:
        logger.error(f"处理用户 {user.id} 在当前群组 {current_group.group_name} 的权限时出错: {str(e)}")

    # 然后检查其他群组的权限
    all_groups = storage.get_all_groups()
    for group in all_groups:
        if group.group_id == current_group.group_id:
            continue  # 跳过当前群组，因为已经处理过了
            
        try:
            # 获取用户在该群组中的成员信息
            chat_member = await context.bot.get_chat_member(group.chat_id, user.id)
            
            # 如果用户是群组成员且没有对应的访问记录，则创建
            if chat_member.status not in ['left', 'kicked', 'banned']:
                access = storage.get_user_group_access(user.id, group.group_id)
                if not access:
                    # 创建新的访问记录
                    access = UserGroupAccess(
                        access_id=len(storage.user_group_access) + 1,
                        user_id=user.id,
                        group_id=group.group_id,
                        start_date=datetime.now(),
                        end_date=None
                    )
                    storage.add_user_group_access(access)
                    logger.info(f"用户 {user.username or user.first_name} (ID: {user.id}) 加入权益群组 {group.group_name}")
                    storage._save_data()
                else:
                    # 更新现有记录的最后活动时间
                    access.last_active = datetime.now()
                    storage._save_data()
            else:
                # 如果用户不在群组中但有访问记录，则移除记录
                access = storage.get_user_group_access(user.id, group.group_id)
                if access:
                    storage.user_group_access.remove(access)
                    logger.info(f"用户 {user.username or user.first_name} (ID: {user.id}) 已离开权益群组 {group.group_name}")
                    storage._save_data()
        except Exception as e:
            logger.error(f"检查用户 {user.id} 在群组 {group.group_name} 的状态时出错: {str(e)}")
            # 尝试重新获取群组成员信息
            try:
                await context.bot.get_chat(group.chat_id)
                logger.info(f"群组 {group.group_name} 仍然可访问，保留错误记录以供后续处理")
            except Exception as chat_error:
                logger.warning(f"群组 {group.group_name} 不可访问，可能已被删除或机器人被移除: {str(chat_error)}")
                # 如果群组不可访问，考虑清理相关的访问记录
                access = storage.get_user_group_access(user.id, group.group_id)
                if access:
                    storage.user_group_access.remove(access)
                    storage._save_data()
                    logger.info(f"已清理用户 {user.id} 在不可访问群组 {group.group_name} 的访问记录")

async def sync_group_members(context: ContextTypes.DEFAULT_TYPE) -> None:
    """定时同步群组成员"""
    storage = Storage()
    
    # 获取所有已知的权益群组
    groups = storage.get_all_groups()
    
    for group in groups:
        try:
            # 获取群组成员
            chat_members = await context.bot.get_chat_administrators(group.chat_id)
            
            # 更新群组成员的访问记录
            for member in chat_members:
                user = member.user
                access = storage.get_user_group_access(user.id, group.group_id)
                
                if not access:
                    # 创建新的访问记录
                    access = UserGroupAccess(
                        access_id=len(storage.user_group_access) + 1,
                        user_id=user.id,
                        group_id=group.group_id,
                        start_date=datetime.now(),
                        end_date=None
                    )
                    storage.add_user_group_access(access)
                    logger.info(f"同步: 用户 {user.username or user.first_name} (ID: {user.id}) 加入权益群组 {group.group_name}")
            
            # 保存数据
            storage._save_data()
                
        except Exception as e:
            logger.error(f"同步权益群组 {group.group_name} (ID: {group.group_id}) 成员失败: {e}")

def get_group_sync_handlers():
    """获取群组同步相关的处理器"""
    return [
        MessageHandler(
            (filters.ChatType.GROUPS | filters.ChatType.CHANNEL) & ~filters.Regex(r"^(积分|积分排行)$"),  # 只处理群组和频道消息，但排除关键词
            handle_user_message
        )
    ] 