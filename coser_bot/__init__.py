"""
@description: Coser社群Bot主模块初始化文件
"""
__version__ = "0.1.0"

import logging
from telegram.ext import Application

from .config import config
from .database import Storage
from .handlers import register_all_handlers
from .utils.group_sync import GroupSyncManager

logger = logging.getLogger(__name__)

async def on_startup(application: Application):
    """机器人启动时的初始化操作"""
    # 同步所有群组成员信息
    sync_manager = application.bot_data.get('group_sync_manager')
    if sync_manager:
        successful_groups = await sync_manager.sync_all_groups()
        logger.info(f"已同步 {len(successful_groups)} 个群组的成员信息")

def create_application() -> Application:
    """创建并配置机器人应用"""
    # 创建应用实例
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # 初始化存储
    storage = Storage()
    application.bot_data['storage'] = storage
    
    # 注册处理器
    register_all_handlers(application)
    
    # 添加启动回调
    application.job_queue.run_once(
        lambda ctx: on_startup(application),
        when=0
    )
    
    return application