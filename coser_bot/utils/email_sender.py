"""
@description: 邮件发送模块，用于发送验证码邮件
"""
import smtplib
import logging
import random
import string
import asyncio
import os
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Tuple, Optional

from ..config.settings import (
    SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, SMTP_FROM_NAME
)

logger = logging.getLogger(__name__)

def generate_verification_code(length: int = 6) -> str:
    """
    @description: 生成随机验证码
    @param {int} length: 验证码长度，默认6位
    @return {str}: 生成的验证码
    """
    return ''.join(random.choices(string.digits, k=length))

async def send_verification_email(email: str, subject: str, message_content: str) -> Tuple[bool, str]:
    """
    发送邮件
    @param email: 目标邮箱
    @param subject: 邮件主题
    @param message_content: 邮件内容
    @return: (是否成功, 错误信息)
    """
    try:
        # 使用settings.py中的配置
        if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]):
            logger.error("邮箱配置不完整")
            return False, "邮箱配置不完整"
        
        # 记录详细信息以便调试
        logger.info(f"准备发送邮件到: {email}")
        logger.info(f"邮件主题: {subject}")
        logger.info(f"邮件内容: {message_content}")
        logger.info(f"发件人名称: {SMTP_FROM_NAME}")
        
        # 创建邮件
        msg = MIMEMultipart()
        
        # 使用纯ASCII字符作为发件人名称，完全避免中文
        msg["From"] = f"Coser Bot <{SMTP_FROM_EMAIL}>"
        msg["To"] = email
        msg["Subject"] = Header(subject, 'utf-8')
        
        # 添加邮件内容，确保使用UTF-8编码
        # 将所有可能的特殊字符替换为普通字符
        clean_message = message_content.replace('\xa0', ' ')
        clean_message = ''.join(c if ord(c) < 128 else ' ' for c in clean_message)
        
        # 记录清理后的内容
        logger.info(f"清理后的邮件内容: {clean_message}")
        
        # 添加纯文本内容
        text_part = MIMEText(clean_message, "plain", 'utf-8')
        msg.attach(text_part)
        
        # 将整个邮件转换为字符串，检查是否有编码问题
        try:
            msg_str = msg.as_string()
            logger.info("邮件转换为字符串成功")
        except Exception as e:
            logger.error(f"邮件转换为字符串失败: {str(e)}")
            return False, f"邮件格式化失败: {str(e)}"
        
        # 连接SMTP服务器并发送邮件
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            # 直接使用sendmail方法
            server.sendmail(SMTP_FROM_EMAIL, [email], msg_str)
        
        logger.info(f"验证码邮件已成功发送至 {email}")
        return True, "邮件发送成功"
        
    except Exception as e:
        error_msg = f"发送邮件时出错: {str(e)}"
        logger.error(error_msg)
        # 打印完整的堆栈跟踪
        logger.error(traceback.format_exc())
        return False, error_msg

def _send_email(server, port, username, password, from_email, to_email, message):
    """
    @description: 实际发送邮件的函数，在线程池中执行
    @param {str} server: SMTP服务器
    @param {int} port: SMTP端口
    @param {str} username: SMTP用户名
    @param {str} password: SMTP密码
    @param {str} from_email: 发件人邮箱
    @param {str} to_email: 收件人邮箱
    @param {str} message: 邮件内容
    """
    with smtplib.SMTP(server, port) as server:
        server.starttls()  # 启用TLS加密
        server.login(username, password)
        server.sendmail(from_email, to_email, message)

def is_valid_email(email: str) -> bool:
    """
    @description: 验证邮箱格式是否有效
    @param {str} email: 邮箱地址
    @return {bool}: 是否有效
    """
    import re
    # 简单的邮箱格式验证
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) 