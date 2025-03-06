"""
@description: 日志管理模块，提供日志轮转和清理功能
"""
import os
import glob
import logging
import logging.handlers
import datetime
import shutil
from pathlib import Path

from ..config.settings import LOG_DIR

logger = logging.getLogger(__name__)

def init_logger():
    """
    初始化日志系统
    """
    # 创建日志目录
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    # 设置日志格式
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(LOG_DIR, 'coser_bot.log'),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10
    )
    file_handler.setFormatter(log_formatter)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    
    # 设置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 全局设置为DEBUG级别
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 特别为coser_bot包设置更详细的日志级别
    coser_bot_logger = logging.getLogger('coser_bot')
    coser_bot_logger.setLevel(logging.DEBUG)
    
    # 设置其他库的日志级别
    logging.getLogger('telegram').setLevel(logging.INFO)
    logging.getLogger('httpx').setLevel(logging.INFO)
    logging.getLogger('apscheduler').setLevel(logging.INFO)
    
    logger = logging.getLogger('coser_bot.utils.log_manager')
    logger.info("日志系统初始化完成，日志文件: " + os.path.abspath(os.path.join(LOG_DIR, 'coser_bot.log')))

def cleanup_old_logs(max_days=30):
    """
    清理旧的日志文件
    
    Args:
        max_days: 保留的最大天数
    """
    try:
        # 获取当前时间
        now = datetime.datetime.now()
        cutoff_date = now - datetime.timedelta(days=max_days)
        
        # 查找所有日志文件
        log_pattern = os.path.join(LOG_DIR, "*.log*")
        log_files = glob.glob(log_pattern)
        
        # 检查每个文件的修改时间
        for log_file in log_files:
            # 跳过当前主日志文件
            if log_file.endswith("coser_bot.log"):
                continue
                
            # 获取文件修改时间
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(log_file))
            
            # 如果文件超过保留期限，则删除
            if file_mtime < cutoff_date:
                os.remove(log_file)
                logger.info(f"删除过期日志文件: {log_file}")
    except Exception as e:
        logger.error(f"清理日志文件失败: {e}")

async def schedule_log_cleanup(context):
    """
    定时清理日志任务
    
    Args:
        context: 上下文对象
    """
    logger.info("执行定时日志清理")
    cleanup_old_logs() 