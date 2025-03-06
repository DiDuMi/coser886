"""
@description: 签到功能测试模块
"""
import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from ..handlers.checkin import process_checkin
from ..database.models import User
from ..config.settings import DAILY_CHECKIN_POINTS, WEEKLY_STREAK_POINTS

# 模拟数据
TEST_USER_ID = 123456789
TEST_USERNAME = "test_user"
TEST_CHAT_ID = -1001234567890
TEST_MESSAGE_ID = 1
TEST_THREAD_ID = 10

@pytest.fixture
def mock_bot():
    """创建模拟Bot对象"""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot

@pytest.fixture
def mock_db():
    """创建模拟数据库对象"""
    with patch("coser_bot.handlers.checkin.Database") as mock_db_class:
        db_instance = mock_db_class.return_value
        db_instance.connect = AsyncMock()
        db_instance.disconnect = AsyncMock()
        db_instance.get_user = AsyncMock()
        db_instance.create_user = AsyncMock()
        db_instance.update_user = AsyncMock()
        db_instance.add_points_transaction = AsyncMock()
        db_instance.add_checkin_record = AsyncMock()
        yield db_instance

@pytest.mark.asyncio
async def test_first_checkin(mock_bot, mock_db):
    """测试首次签到"""
    # 模拟用户不存在
    mock_db.get_user.return_value = None
    
    # 执行签到
    await process_checkin(
        mock_bot, 
        TEST_USER_ID, 
        TEST_USERNAME, 
        TEST_CHAT_ID, 
        TEST_MESSAGE_ID, 
        TEST_THREAD_ID
    )
    
    # 验证创建用户
    mock_db.create_user.assert_called_once()
    created_user = mock_db.create_user.call_args[0][0]
    assert created_user.user_id == TEST_USER_ID
    assert created_user.username == TEST_USERNAME
    
    # 验证更新用户
    mock_db.update_user.assert_called_once()
    updated_user = mock_db.update_user.call_args[0][0]
    assert updated_user.points == DAILY_CHECKIN_POINTS
    assert updated_user.streak_days == 1
    assert updated_user.last_checkin_date == date.today()
    
    # 验证添加积分交易
    mock_db.add_points_transaction.assert_called_once()
    
    # 验证添加签到记录
    mock_db.add_checkin_record.assert_called_once()
    
    # 验证发送消息
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]['chat_id'] == TEST_CHAT_ID
    assert mock_bot.send_message.call_args[1]['reply_to_message_id'] == TEST_MESSAGE_ID
    assert mock_bot.send_message.call_args[1]['message_thread_id'] == TEST_THREAD_ID

@pytest.mark.asyncio
async def test_consecutive_checkin(mock_bot, mock_db):
    """测试连续签到"""
    # 模拟用户存在，昨天签到过
    yesterday = date.today() - timedelta(days=1)
    user = User(
        user_id=TEST_USER_ID,
        username=TEST_USERNAME,
        last_checkin_date=yesterday,
        streak_days=1,
        points=100
    )
    mock_db.get_user.return_value = user
    
    # 执行签到
    await process_checkin(
        mock_bot, 
        TEST_USER_ID, 
        TEST_USERNAME, 
        TEST_CHAT_ID, 
        TEST_MESSAGE_ID, 
        TEST_THREAD_ID
    )
    
    # 验证更新用户
    mock_db.update_user.assert_called_once()
    updated_user = mock_db.update_user.call_args[0][0]
    assert updated_user.points == 100 + DAILY_CHECKIN_POINTS
    assert updated_user.streak_days == 2
    assert updated_user.last_checkin_date == date.today()
    
    # 验证添加积分交易
    mock_db.add_points_transaction.assert_called_once()
    
    # 验证添加签到记录
    mock_db.add_checkin_record.assert_called_once()
    
    # 验证发送消息
    mock_bot.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_streak_bonus(mock_bot, mock_db):
    """测试连续签到奖励"""
    # 模拟用户存在，已连续签到6天
    yesterday = date.today() - timedelta(days=1)
    user = User(
        user_id=TEST_USER_ID,
        username=TEST_USERNAME,
        last_checkin_date=yesterday,
        streak_days=6,
        points=100
    )
    mock_db.get_user.return_value = user
    
    # 执行签到
    await process_checkin(
        mock_bot, 
        TEST_USER_ID, 
        TEST_USERNAME, 
        TEST_CHAT_ID, 
        TEST_MESSAGE_ID, 
        TEST_THREAD_ID
    )
    
    # 验证更新用户
    mock_db.update_user.assert_called_once()
    updated_user = mock_db.update_user.call_args[0][0]
    assert updated_user.points == 100 + DAILY_CHECKIN_POINTS + WEEKLY_STREAK_POINTS
    assert updated_user.streak_days == 7
    assert updated_user.last_checkin_date == date.today()
    
    # 验证添加积分交易（应该有两笔交易）
    assert mock_db.add_points_transaction.call_count == 2
    
    # 验证添加签到记录
    mock_db.add_checkin_record.assert_called_once()
    
    # 验证发送消息
    mock_bot.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_already_checked_in(mock_bot, mock_db):
    """测试重复签到"""
    # 模拟用户存在，今天已经签到
    today = date.today()
    user = User(
        user_id=TEST_USER_ID,
        username=TEST_USERNAME,
        last_checkin_date=today,
        streak_days=1,
        points=100
    )
    mock_db.get_user.return_value = user
    
    # 执行签到
    await process_checkin(
        mock_bot, 
        TEST_USER_ID, 
        TEST_USERNAME, 
        TEST_CHAT_ID, 
        TEST_MESSAGE_ID, 
        TEST_THREAD_ID
    )
    
    # 验证没有更新用户
    mock_db.update_user.assert_not_called()
    
    # 验证没有添加积分交易
    mock_db.add_points_transaction.assert_not_called()
    
    # 验证没有添加签到记录
    mock_db.add_checkin_record.assert_not_called()
    
    # 验证发送消息（提示已经签到）
    mock_bot.send_message.assert_called_once()
    assert "今天已经签到过" in mock_bot.send_message.call_args[1]['text'] 