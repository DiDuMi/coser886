"""
@description: 数据库备份模块，提供自动备份功能
"""
import os
import shutil
import logging
import datetime
import glob
from pathlib import Path

from ..config.settings import (
    DATA_DIR, BACKUP_DIR, AUTO_BACKUP_ENABLED,
    AUTO_BACKUP_INTERVAL_HOURS, MAX_BACKUP_COUNT
)

logger = logging.getLogger(__name__)

def backup_database() -> bool:
    """
    备份数据库文件
    
    Returns:
        bool: 备份是否成功
    """
    try:
        # 确保备份目录存在
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # 数据库文件路径
        db_file = os.path.join(DATA_DIR, "coser_bot.db")
        
        # 如果数据库文件不存在，则无需备份
        if not os.path.exists(db_file):
            logger.warning("数据库文件不存在，无法进行备份")
            return False
        
        # 生成备份文件名，包含时间戳
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"coser_bot_{timestamp}.db")
        
        # 复制数据库文件
        shutil.copy2(db_file, backup_file)
        logger.info(f"数据库备份成功: {backup_file}")
        
        # 清理旧备份
        cleanup_old_backups()
        
        return True
    except Exception as e:
        logger.error(f"数据库备份失败: {e}")
        return False

def cleanup_old_backups() -> None:
    """
    清理旧的备份文件，只保留最近的MAX_BACKUP_COUNT个备份
    """
    try:
        # 获取所有备份文件
        backup_pattern = os.path.join(BACKUP_DIR, "coser_bot_*.db")
        backup_files = glob.glob(backup_pattern)
        
        # 按修改时间排序
        backup_files.sort(key=os.path.getmtime)
        
        # 如果备份文件数量超过限制，删除最旧的文件
        if len(backup_files) > MAX_BACKUP_COUNT:
            files_to_delete = backup_files[:-MAX_BACKUP_COUNT]
            for file in files_to_delete:
                os.remove(file)
                logger.info(f"删除旧备份文件: {file}")
    except Exception as e:
        logger.error(f"清理旧备份文件失败: {e}")

async def schedule_backup(context) -> None:
    """
    定时备份任务
    
    Args:
        context: 上下文对象
    """
    if AUTO_BACKUP_ENABLED:
        logger.info("执行定时数据库备份")
        backup_database()
    else:
        logger.debug("自动备份已禁用，跳过备份任务") 