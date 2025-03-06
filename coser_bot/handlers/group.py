from telegram import Update
from telegram.ext import ContextTypes, ChatMemberHandler
from telegram.constants import ChatMemberStatus

from ..utils.group_sync import GroupSyncManager

async def handle_chat_member_updated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理群组成员更新事件"""
    if not update.chat_member:
        return
        
    chat_id = update.chat_member.chat.id
    user_id = update.chat_member.new_chat_member.user.id
    new_status = update.chat_member.new_chat_member.status
    
    # 获取 GroupSyncManager 实例
    sync_manager = context.bot_data.get('group_sync_manager')
    if not sync_manager:
        return
        
    # 判断成员状态
    is_member = new_status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.BANNED]
    is_admin = new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    
    # 更新成员状态
    await sync_manager.handle_member_update(
        group_id=chat_id,
        user_id=user_id,
        is_member=is_member,
        is_admin=is_admin
    )

def register_handlers(application):
    """注册群组相关的处理器"""
    application.add_handler(ChatMemberHandler(handle_chat_member_updated))
    
    # 创建并存储 GroupSyncManager 实例
    sync_manager = GroupSyncManager(application.bot, application.bot_data['storage'])
    application.bot_data['group_sync_manager'] = sync_manager 