"""
@description: 健康检查模块，提供机器人状态监控功能
"""
import os
import time
import psutil
import logging
import platform
import sqlite3
from datetime import datetime

from ..config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)

class HealthCheck:
    """健康检查类，提供各种系统状态检查方法"""
    
    @staticmethod
    def check_system_resources():
        """
        检查系统资源使用情况
        
        Returns:
            dict: 系统资源信息
        """
        try:
            # 获取CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 获取内存使用情况
            memory = psutil.virtual_memory()
            memory_used_mb = memory.used / (1024 * 1024)
            memory_total_mb = memory.total / (1024 * 1024)
            memory_percent = memory.percent
            
            # 获取磁盘使用情况
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / (1024 * 1024 * 1024)
            disk_total_gb = disk.total / (1024 * 1024 * 1024)
            disk_percent = disk.percent
            
            # 获取进程信息
            process = psutil.Process(os.getpid())
            process_memory_mb = process.memory_info().rss / (1024 * 1024)
            process_cpu_percent = process.cpu_percent(interval=1)
            process_threads = process.num_threads()
            process_create_time = datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S')
            process_running_time = time.time() - process.create_time()
            
            # 返回结果
            return {
                "system": {
                    "platform": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "processor": platform.processor(),
                    "python_version": platform.python_version(),
                },
                "resources": {
                    "cpu_percent": cpu_percent,
                    "memory_used_mb": round(memory_used_mb, 2),
                    "memory_total_mb": round(memory_total_mb, 2),
                    "memory_percent": memory_percent,
                    "disk_used_gb": round(disk_used_gb, 2),
                    "disk_total_gb": round(disk_total_gb, 2),
                    "disk_percent": disk_percent,
                },
                "process": {
                    "pid": os.getpid(),
                    "memory_mb": round(process_memory_mb, 2),
                    "cpu_percent": process_cpu_percent,
                    "threads": process_threads,
                    "create_time": process_create_time,
                    "running_time_seconds": round(process_running_time, 2),
                    "running_time_formatted": HealthCheck.format_time_duration(process_running_time),
                }
            }
        except Exception as e:
            logger.error(f"检查系统资源时出错: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def check_database():
        """
        检查数据库状态
        
        Returns:
            dict: 数据库状态信息
        """
        try:
            # 检查数据库文件是否存在
            if not os.path.exists(DATABASE_PATH):
                return {"status": "error", "message": "数据库文件不存在"}
            
            # 获取数据库文件大小
            db_size_mb = os.path.getsize(DATABASE_PATH) / (1024 * 1024)
            
            # 连接数据库并获取表信息
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            # 获取各表的记录数
            table_counts = {}
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                table_counts[table_name] = count
            
            # 关闭连接
            conn.close()
            
            # 返回结果
            return {
                "status": "ok",
                "file_size_mb": round(db_size_mb, 2),
                "tables": len(tables),
                "table_counts": table_counts,
                "last_modified": datetime.fromtimestamp(os.path.getmtime(DATABASE_PATH)).strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"检查数据库时出错: {e}")
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def format_time_duration(seconds):
        """
        格式化时间间隔
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化后的时间字符串
        """
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{int(days)}天")
        if hours > 0 or days > 0:
            parts.append(f"{int(hours)}小时")
        if minutes > 0 or hours > 0 or days > 0:
            parts.append(f"{int(minutes)}分钟")
        parts.append(f"{int(seconds)}秒")
        
        return "".join(parts)

async def health_check_command(update, context):
    """
    健康检查命令处理函数
    
    Args:
        update: 更新对象
        context: 上下文对象
    """
    # 检查是否是管理员
    from ..config.config import config
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        await update.message.reply_text("⚠️ 只有管理员可以执行此命令")
        return
    
    # 发送等待消息
    message = await update.message.reply_text("⏳ 正在收集系统状态信息，请稍候...")
    
    try:
        # 获取系统资源信息
        system_info = HealthCheck.check_system_resources()
        
        # 获取数据库状态
        db_info = HealthCheck.check_database()
        
        # 构建响应消息
        response = f"""
📊 <b>系统状态报告</b>

<b>系统信息:</b>
• 平台: {system_info['system']['platform']} {system_info['system']['release']}
• Python版本: {system_info['system']['python_version']}

<b>资源使用情况:</b>
• CPU使用率: {system_info['resources']['cpu_percent']}%
• 内存使用: {system_info['resources']['memory_used_mb']}/{system_info['resources']['memory_total_mb']} MB ({system_info['resources']['memory_percent']}%)
• 磁盘使用: {system_info['resources']['disk_used_gb']}/{system_info['resources']['disk_total_gb']} GB ({system_info['resources']['disk_percent']}%)

<b>机器人进程:</b>
• PID: {system_info['process']['pid']}
• 内存占用: {system_info['process']['memory_mb']} MB
• CPU使用率: {system_info['process']['cpu_percent']}%
• 线程数: {system_info['process']['threads']}
• 启动时间: {system_info['process']['create_time']}
• 运行时长: {system_info['process']['running_time_formatted']}

<b>数据库状态:</b>
• 状态: {'正常' if db_info['status'] == 'ok' else '错误: ' + db_info.get('message', '未知错误')}
• 文件大小: {db_info.get('file_size_mb', 'N/A')} MB
• 表数量: {db_info.get('tables', 'N/A')}
• 最后修改: {db_info.get('last_modified', 'N/A')}

<b>表记录数:</b>
"""
        
        # 添加表记录数信息
        if db_info['status'] == 'ok' and 'table_counts' in db_info:
            for table, count in db_info['table_counts'].items():
                response += f"• {table}: {count}条记录\n"
        
        # 发送响应
        await message.edit_text(response, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"执行健康检查命令时出错: {e}")
        await message.edit_text(f"❌ 执行健康检查时出错: {str(e)}")

def get_health_check_handlers():
    """
    获取健康检查相关的处理器
    
    Returns:
        list: 处理器列表
    """
    from telegram.ext import CommandHandler
    
    return [
        CommandHandler("health", health_check_command),
        CommandHandler("status", health_check_command),
    ] 