"""
@description: 处理器模块初始化文件
"""
from telegram.ext import CommandHandler

def register_all_handlers(application):
    """注册所有处理器"""
    from .checkin import get_checkin_handlers
    from .points import get_points_handlers
    from .email import get_email_handlers
    from .recover import get_recovery_handlers
    from .admin import get_admin_handlers
    from .leaderboard import get_leaderboard_handlers
    
    # 基本命令
    from ..simple_bot import start_command, help_command, my_info_command
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myinfo", my_info_command))
    
    # 签到相关处理器
    for handler in get_checkin_handlers():
        application.add_handler(handler)
    
    # 积分相关处理器
    for handler in get_points_handlers():
        application.add_handler(handler)
    
    # 邮箱相关处理器
    for handler in get_email_handlers():
        application.add_handler(handler)
    
    # 恢复请求相关处理器
    for handler in get_recovery_handlers():
        application.add_handler(handler)
        
    # 管理员相关处理器
    for handler in get_admin_handlers():
        application.add_handler(handler)
        
    # 排行榜相关处理器
    for handler in get_leaderboard_handlers():
        application.add_handler(handler) 