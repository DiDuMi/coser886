import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update, CallbackQuery, User, Chat, Bot
from telegram.ext import ContextTypes

from coser_bot.database.models import Group, UserGroupAccess, RecoveryRequest, RecoveryStatus
from coser_bot.database.storage import Storage
from coser_bot.handlers.recover import generate_invite_links, approve_recovery_callback

@pytest.fixture
def mock_storage():
    storage = MagicMock(spec=Storage)
    storage.groups = {
        1: Group(group_id=1, group_name="测试群组1", is_paid=True, required_points=100),
        2: Group(group_id=2, group_name="测试群组2", is_paid=True, required_points=200)
    }
    return storage

@pytest.fixture
def mock_bot():
    bot = AsyncMock(spec=Bot)
    bot.create_chat_invite_link.return_value = MagicMock(invite_link="https://t.me/test_invite_link")
    return bot

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.callback_query = MagicMock(spec=CallbackQuery)
    update.callback_query.from_user = MagicMock(spec=User, id=999, username="admin")
    update.callback_query.data = "approve:test_request_id"
    return update

@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock(spec=Bot)
    context.bot.send_message = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_generate_invite_links(mock_bot, mock_storage):
    """测试生成邀请链接功能"""
    groups = [
        Group(group_id=1, group_name="测试群组1", is_paid=True, required_points=100),
        Group(group_id=2, group_name="测试群组2", is_paid=True, required_points=200)
    ]
    
    with patch("coser_bot.handlers.recover.Storage", return_value=mock_storage):
        mock_storage.add_invite_link.return_value = True
        invite_links = await generate_invite_links(mock_bot, 123, groups)
        
        assert len(invite_links) == 2
        assert all(link == "https://t.me/test_invite_link" for link in invite_links.values())
        assert mock_bot.create_chat_invite_link.call_count == 2
        assert mock_storage.add_invite_link.call_count == 2

@pytest.mark.asyncio
async def test_approve_recovery_callback(mock_update, mock_context, mock_storage):
    """测试批准恢复请求的回调函数"""
    recovery_request = RecoveryRequest(
        request_id="test_request_id",
        old_user_id=123,
        new_user_id=456,
        email="test@example.com",
        reason="测试原因"
    )
    
    user_group_accesses = [
        UserGroupAccess(user_id=123, group_id=1),
        UserGroupAccess(user_id=123, group_id=2)
    ]
    
    with patch("coser_bot.handlers.recover.Storage", return_value=mock_storage):
        mock_storage.get_recovery_request.return_value = recovery_request
        mock_storage.update_recovery_request.return_value = True
        mock_storage.get_user_group_accesses.return_value = user_group_accesses
        mock_storage.get_group.side_effect = lambda gid: mock_storage.groups.get(gid)
        
        await approve_recovery_callback(mock_update, mock_context)
        
        # 验证恢复请求状态更新
        assert mock_storage.update_recovery_request.call_count == 1
        assert recovery_request.status == RecoveryStatus.APPROVED
        
        # 验证邀请链接生成和发送
        assert mock_context.bot.send_message.call_count == 1
        assert mock_update.callback_query.answer.call_count == 1 