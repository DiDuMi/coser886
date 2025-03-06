from datetime import datetime
import logging
from typing import Optional, List

from telegram import Bot, ChatMember
from telegram.error import TelegramError

from ..database.models import UserGroupAccess, Group
from ..database.storage import Storage

logger = logging.getLogger(__name__)

class GroupSyncManager:
    def __init__(self, bot: Bot, storage: Storage):
        self.bot = bot
        self.storage = storage

    async def sync_group_members(self, group_id: int) -> bool:
        """
        同步指定群组的所有成员信息
        
        Args:
            group_id: 群组ID
            
        Returns:
            bool: 同步是否成功
        """
        try:
            # 获取群组信息
            group = self.storage.get_group(group_id)
            if not group:
                logger.error(f"群组不存在: {group_id}")
                return False

            # 获取现有的群组访问权限记录
            existing_accesses = {
                access.user_id: access
                for access in self.storage.get_group_user_accesses(group_id)
            }

            # 获取群组所有成员
            try:
                chat_members = await self.bot.get_chat_administrators(group_id)
                # 添加普通成员
                members = await self.bot.get_chat_members_count(group_id)
                if members > len(chat_members):
                    # TODO: 实现分页获取普通成员
                    pass
            except TelegramError as e:
                logger.error(f"获取群组 {group_id} 成员失败: {e}")
                return False

            # 更新管理员成员记录
            for member in chat_members:
                await self._update_member_access(group_id, member, existing_accesses)

            logger.info(f"已同步群组 {group_id} 的成员信息")
            return True

        except Exception as e:
            logger.error(f"同步群组 {group_id} 成员时发生错误: {e}")
            return False

    async def sync_all_groups(self) -> List[int]:
        """
        同步所有群组的成员信息
        
        Returns:
            List[int]: 同步成功的群组ID列表
        """
        successful_groups = []
        groups = self.storage.get_all_groups()
        
        for group in groups:
            if await self.sync_group_members(group.group_id):
                successful_groups.append(group.group_id)
            
        return successful_groups

    async def _update_member_access(
        self, 
        group_id: int, 
        member: ChatMember,
        existing_accesses: dict
    ) -> None:
        """
        更新单个成员的访问权限记录
        """
        user_id = member.user.id
        
        # 检查是否已存在访问记录
        existing_access = existing_accesses.get(user_id)
        
        if not existing_access:
            # 创建新的访问记录
            access = UserGroupAccess(
                user_id=user_id,
                group_id=group_id,
                joined_at=datetime.now(),
                is_admin=member.status in ['administrator', 'creator']
            )
            self.storage.add_user_group_access(access)
        else:
            # 更新现有记录
            existing_access.is_admin = member.status in ['administrator', 'creator']
            existing_access.last_active = datetime.now()
            self.storage.update_user_group_access(existing_access)

    async def handle_member_update(
        self, 
        group_id: int, 
        user_id: int, 
        is_member: bool,
        is_admin: bool = False
    ) -> None:
        """
        处理成员更新事件
        
        Args:
            group_id: 群组ID
            user_id: 用户ID
            is_member: 是否为成员
            is_admin: 是否为管理员
        """
        try:
            access = self.storage.get_user_group_access(user_id, group_id)
            
            if is_member:
                if not access:
                    # 添加新成员记录
                    access = UserGroupAccess(
                        user_id=user_id,
                        group_id=group_id,
                        joined_at=datetime.now(),
                        is_admin=is_admin
                    )
                    self.storage.add_user_group_access(access)
                else:
                    # 更新现有记录
                    access.is_admin = is_admin
                    access.last_active = datetime.now()
                    self.storage.update_user_group_access(access)
            else:
                # 成员离开群组，删除记录
                if access:
                    self.storage.remove_user_group_access(access)
                    
            logger.info(f"已更新用户 {user_id} 在群组 {group_id} 的成员状态")
            
        except Exception as e:
            logger.error(f"更新成员状态失败: {e}") 