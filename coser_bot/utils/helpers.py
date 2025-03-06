"""
@description: 辅助函数模块，提供各种通用工具函数
"""
import random
import string
import logging
import re
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def generate_verification_code(length: int = 6) -> str:
    """
    @description: 生成随机验证码
    @param {int} length: 验证码长度
    @return {str}: 生成的验证码
    """
    return ''.join(random.choices(string.digits, k=length))

def is_valid_email(email: str) -> bool:
    """
    @description: 验证邮箱格式是否有效
    @param {str} email: 邮箱地址
    @return {bool}: 是否有效
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def format_number(number: int) -> str:
    """
    @description: 格式化数字，添加千位分隔符
    @param {int} number: 要格式化的数字
    @return {str}: 格式化后的字符串
    """
    return f"{number:,}"

def parse_gift_command(text: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    @description: 解析赠送积分命令
    @param {str} text: 命令文本
    @return {Tuple[Optional[str], Optional[int], Optional[str]]}: (用户名, 积分数量, 备注)
    """
    # 匹配格式: 赠送 @username 100 感谢分享
    username_pattern = r'赠送\s+@(\w+)\s+(\d+)(?:\s+(.+))?'
    username_match = re.match(username_pattern, text)
    
    if username_match:
        username = username_match.group(1)
        points = int(username_match.group(2))
        reason = username_match.group(3) or "无备注"
        return username, points, reason
    
    # 匹配格式: 赠送 100 感谢分享 (用于回复消息)
    reply_pattern = r'赠送\s+(\d+)(?:\s+(.+))?'
    reply_match = re.match(reply_pattern, text)
    
    if reply_match:
        points = int(reply_match.group(1))
        reason = reply_match.group(2) or "无备注"
        return None, points, reason
    
    return None, None, None

def calculate_expiry_time(minutes: int = 10) -> datetime:
    """
    @description: 计算过期时间
    @param {int} minutes: 有效期分钟数
    @return {datetime}: 过期时间
    """
    return datetime.now() + timedelta(minutes=minutes)

def is_admin(user_id: int, admin_ids: list) -> bool:
    """
    @description: 检查用户是否为管理员
    @param {int} user_id: 用户ID
    @param {list} admin_ids: 管理员ID列表
    @return {bool}: 是否为管理员
    """
    return user_id in admin_ids 