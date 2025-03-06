"""
@name: simple_bot.py
@description: Coser社群机器人启动脚本
@version: 1.0.0
@author: Coser开发团队
@created: 2024-03-01
@updated: 2024-03-21
@description: 这个脚本用于启动Coser社群机器人，处理机器人的命令和回调，并提供用户交互界面。
             主要功能包括：用户签到、积分管理、排行榜、邮箱绑定等。
"""

# 标准库导入
import os
import sys
import logging
import asyncio
import platform
from datetime import datetime, date
import tempfile
import atexit
import shutil
import time
import ctypes
import glob

# 第三方库导入
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.request import HTTPXRequest

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# 添加当前目录到系统路径，确保能找到模块
sys.path.append(os.getcwd())

# 项目模块导入
from coser_bot import config
from coser_bot.utils.log_manager import init_logger
from coser_bot.database.storage import Storage
from coser_bot.config.constants import TEMPLATES
from coser_bot.database.models import (
    User,
    CheckinRecord,
    PointsTransaction,
    TransactionStatus,
    UserGroupAccess
)
from coser_bot.handlers.checkin import get_checkin_handlers
from coser_bot.handlers.points import get_points_handlers, get_user_points_info, format_number
from coser_bot.handlers.email import get_email_handlers, bind_email_command
from coser_bot.handlers.recover import get_recovery_handlers
from coser_bot.handlers.admin import get_admin_handlers, ADMIN_IDS
from coser_bot.handlers.leaderboard import get_leaderboard_handlers, handle_leaderboard_callback
from coser_bot.handlers.group_sync import get_group_sync_handlers, sync_group_members

# 配置日志
init_logger()
logger = logging.getLogger(__name__)

# 设置Windows平台的事件循环策略
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 辅助函数
def format_number(number: int) -> str:
    """格式化数字，添加千位分隔符"""
    return "{:,}".format(number)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理/start命令
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    user = update.effective_user
    
    # 获取存储对象
    storage = Storage()
    
    # 检查用户是否已存在
    db_user = storage.get_user(user.id)
    is_new_user = not db_user
    
    if is_new_user:
        # 创建新用户
        db_user = User(
            user_id=user.id,
            username=user.username or user.first_name,
            first_name=user.first_name,
            join_date=datetime.now(),
            points=0
        )
        storage.save_user(db_user)
        logger.info(f"创建新用户: {db_user.username} (ID: {db_user.user_id})")
    else:
        logger.info(f"欢迎回来: {db_user.username} (ID: {db_user.user_id})")
        
    # 记录用户活动
    await record_user_activity(db_user)
    
    # 获取用户名称
    name = user.first_name
    
    # 构建欢迎消息
    if is_new_user:
        welcome_text = f"""
<b>🌟 欢迎加入 Coser 社群！</b>

亲爱的 <b>{name}</b>，很高兴认识你！
我是你的专属社群助手，让我们一起开启精彩社群之旅吧！

<b>✨ 新手入门</b>
• 发送 /checkin 完成首次签到获得双倍积分
• 使用 /bindemail 绑定邮箱获得50积分奖励
• 查看 /rank 了解社群活跃度排名

<b>💡 实用小贴士</b>
• 每日签到可累积连续签到奖励
• 绑定邮箱可保障账号安全
• 使用 /gift 可与好友分享积分

<b>🚀 立即开始</b>
点击下方按钮体验社群功能，或发送 /checkin 立即获取积分！
"""
    else:
        welcome_text = f"""
<b>👋 欢迎回来，{name}！</b>

很高兴再次见到你！以下是你可能感兴趣的功能：

<b>📊 个人状态</b>
• 当前积分: {db_user.points}
• 邮箱绑定: {'已绑定 ✅' if db_user.email and db_user.email_verified else '未绑定 ❌'}
• 上次签到: {db_user.last_checkin.strftime('%Y-%m-%d') if db_user.last_checkin else '暂无记录'}

<b>🔥 热门功能</b>
• /checkin - 每日签到领取积分
• /points - 查看当前积分详情
• /rank - 查看社群排行榜

<b>✨ 今日提示</b>
{'别忘了今天签到哦！' if not db_user.last_checkin or db_user.last_checkin.date() != datetime.now().date() else '今天已完成签到，明天再来吧！'}
"""

    # 创建快捷操作按钮 - 根据新旧用户状态提供不同的按钮布局
    if is_new_user:
        keyboard = [
            [
                InlineKeyboardButton("✅ 立即签到", callback_data="checkin"),
                InlineKeyboardButton("📧 绑定邮箱", callback_data="bindemail")
            ],
            [
                InlineKeyboardButton("📊 社群排行", callback_data="leaderboard_points"),
                InlineKeyboardButton("❓ 新手指南", callback_data="help")
            ],
            [
                InlineKeyboardButton("🎁 每日任务", callback_data="daily_tasks"),
                InlineKeyboardButton("👤 个人中心", callback_data="myinfo")
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("✅ 每日签到", callback_data="checkin"),
                InlineKeyboardButton("💰 我的积分", callback_data="points")
            ],
            [
                InlineKeyboardButton("🏆 社群排行", callback_data="leaderboard_points"),
                InlineKeyboardButton("❓ 帮助指南", callback_data="help")
            ],
            [
                InlineKeyboardButton("👥 邀请好友", callback_data="invite_friends"),
                InlineKeyboardButton("👤 个人中心", callback_data="myinfo")
            ]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 只发送一条消息，带有按钮
    try:
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        logger.info(f"发送欢迎消息给用户 {user.username} (ID: {user.id})")
    except Exception as e:
        logger.error(f"发送欢迎消息时出错: {e}", exc_info=True)
        await update.message.reply_text("欢迎使用机器人！出现了一些问题，请稍后再试。")

def get_main_keyboard() -> InlineKeyboardMarkup:
    """
    创建主菜单键盘
    
    Returns:
        InlineKeyboardMarkup: 包含主菜单按钮的键盘
    """
    keyboard = [
        [
            InlineKeyboardButton("📝 每日签到", callback_data="checkin"),
            InlineKeyboardButton("💰 查看积分", callback_data="points")
        ],
        [
            InlineKeyboardButton("🏆 排行榜", callback_data="leaderboard_points"),
            InlineKeyboardButton("📧 绑定邮箱", callback_data="bindemail")
        ],
        [
            InlineKeyboardButton("❓ 帮助指南", callback_data="help"),
            InlineKeyboardButton("👤 个人信息", callback_data="myinfo")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def record_user_activity(user: User) -> None:
    """
    记录用户活动，更新最后活动时间和登录天数
    
    Args:
        user: 用户对象
    """
    try:
        current_time = datetime.now()
        
        # 如果用户之前没有活动记录，或者上次活动是在不同的日期
        if not user.last_active or user.last_active.date() != current_time.date():
            # 增加登录天数
            user.login_days += 1
            logger.info(f"用户 {user.username} (ID: {user.user_id}) 登录天数增加到 {user.login_days}")
        
        # 更新最后活动时间
        user.last_active = current_time
        
        # 保存用户数据
        storage = Storage()
        storage.save_user(user)
        logger.debug(f"已更新用户 {user.username} (ID: {user.user_id}) 的活动记录，最后活动时间: {current_time}")
    except Exception as e:
        logger.error(f"记录用户活动失败: {e}", exc_info=True)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理/help命令，显示帮助信息
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    help_text = TEMPLATES["help_message"]
    
    # 生成内联键盘
    keyboard = [
        [
            InlineKeyboardButton("📝 每日签到", callback_data="checkin"),
            InlineKeyboardButton("🏆 查看排行", callback_data="leaderboard_points")
        ],
        [
            InlineKeyboardButton("💰 积分管理", callback_data="points"),
            InlineKeyboardButton("👤 个人信息", callback_data="myinfo")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查是否是通过按钮回调调用
    if update.callback_query:
        await update.callback_query.message.reply_text(
            help_text, 
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            help_text, 
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

async def my_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理/myinfo命令，显示用户信息
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    # 检查是否是通过按钮回调调用
    if update.callback_query:
        query = update.callback_query
        user_id = query.from_user.id
        
        # 获取用户信息
        storage = Storage()
        user = storage.get_user(user_id)
        if not user:
            await query.message.reply_text("未找到您的用户信息。")
            return
        
        # 获取所有权益群组
        all_groups = storage.get_all_groups()
        user_groups = []
        
        # 记录调试信息
        logger.info(f"正在检查用户 {user.username} (ID: {user_id}) 的群组权限")
        logger.info(f"系统中配置的群组总数: {len(all_groups)}")
        
        # 发送加载消息
        loading_message = await query.message.reply_text(
            "⏳ 正在加载个人信息...",
            parse_mode=ParseMode.HTML
        )
        
        # 检查用户在每个群组中的成员身份
        for group in all_groups:
            try:
                logger.info(f"检查群组: {group.group_name} (ID: {group.group_id}, chat_id: {group.chat_id})")
                
                # 获取用户在该群组中的成员信息
                chat_member = await context.bot.get_chat_member(group.chat_id, user_id)
                
                # 记录用户在该群组中的状态
                logger.info(f"用户在群组 {group.group_name} 中的状态: {chat_member.status}")
                
                # 如果用户是群组成员
                if chat_member.status not in ['left', 'kicked', 'banned']:
                    user_groups.append(group)
                    # 检查是否有访问记录，如果没有就创建
                    access = storage.get_user_group_access(user_id, group.group_id)
                    if not access:
                        logger.info(f"为用户创建新的群组访问记录: {group.group_name}")
                        access = UserGroupAccess(
                            access_id=len(storage.user_group_access) + 1,
                            user_id=user_id,
                            group_id=group.group_id,
                            start_date=datetime.now(),
                            end_date=None
                        )
                        storage.add_user_group_access(access)
                        storage._save_data()
                        logger.info(f"已保存用户 {user.username} 的群组 {group.group_name} 访问记录")
            except Exception as e:
                logger.error(f"检查用户 {user_id} 在群组 {group.group_name} 的状态时出错: {str(e)}")
                continue
        
        # 记录找到的群组数量
        logger.info(f"用户 {user.username} 共在 {len(user_groups)} 个群组中")
        
        # 构建群组信息文本
        groups_text = "无" if not user_groups else "\n".join([f"• {group.group_name}" for group in user_groups])
        
        # 构建用户信息文本
        info_text = f"""
<b>👤 个人信息</b>

<b>基本信息</b>
• 用户名：{user.username}
• 注册时间：{user.join_date.strftime('%Y-%m-%d')}

<b>积分状态</b>
• 当前积分：<b>{format_number(user.points)}</b> 积分
• 冻结积分：{format_number(user.frozen_points)} 积分

<b>签到记录</b>
• 连续签到：<b>{format_number(user.streak_days)}</b> 天
• 历史最长：{format_number(user.max_streak_days)} 天
• 本月签到：{format_number(user.monthly_checkins)} 次
• 总签到数：{format_number(user.total_checkins)} 次
• 补签机会：{format_number(user.makeup_chances)} 次

<b>账号绑定</b>
• 邮箱：{user.email or '未绑定'} 
• 验证状态：{'✅ 已验证' if user.email_verified else '❌ 未验证'}

<b>权益群组</b>
{groups_text}
"""
        
        # 创建快捷操作按钮
        keyboard = [
            [
                InlineKeyboardButton("📝 每日签到", callback_data="checkin"),
                InlineKeyboardButton("🏆 查看排行", callback_data="leaderboard_points")
            ],
            [
                InlineKeyboardButton("📧 绑定邮箱", callback_data="bindemail"),
                InlineKeyboardButton("🔄 刷新信息", callback_data="myinfo")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 更新加载消息
        await loading_message.edit_text(
            info_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        # 在命令执行完成后打印汇总信息
        logger.info(f"my_info_command 执行完成，用户 {user.username} 的群组权限检查结果：{len(user_groups)} 个群组")
        
    else:
        # 原始的命令处理逻辑
        if not update.effective_user:
            return
            
        user_id = update.effective_user.id
        storage = Storage()
        
        # 获取用户信息
        user = storage.get_user(user_id)
        if not user:
            await update.message.reply_text("未找到您的用户信息。")
            return
        
        # 获取所有权益群组
        all_groups = storage.get_all_groups()
        user_groups = []
        
        # 记录调试信息
        logger.info(f"正在检查用户 {user.username} (ID: {user_id}) 的群组权限")
        logger.info(f"系统中配置的群组总数: {len(all_groups)}")
        
        # 发送加载消息
        loading_message = await update.message.reply_text(
            "⏳ 正在加载个人信息...",
            parse_mode=ParseMode.HTML
        )
        
        # 检查用户在每个群组中的成员身份
        for group in all_groups:
            try:
                logger.info(f"检查群组: {group.group_name} (ID: {group.group_id}, chat_id: {group.chat_id})")
                
                # 获取用户在该群组中的成员信息
                chat_member = await context.bot.get_chat_member(group.chat_id, user_id)
                
                # 记录用户在该群组中的状态
                logger.info(f"用户在群组 {group.group_name} 中的状态: {chat_member.status}")
                
                # 如果用户是群组成员
                if chat_member.status not in ['left', 'kicked', 'banned']:
                    user_groups.append(group)
                    # 检查是否有访问记录，如果没有就创建
                    access = storage.get_user_group_access(user_id, group.group_id)
                    if not access:
                        logger.info(f"为用户创建新的群组访问记录: {group.group_name}")
                        access = UserGroupAccess(
                            access_id=len(storage.user_group_access) + 1,
                            user_id=user_id,
                            group_id=group.group_id,
                            start_date=datetime.now(),
                            end_date=None
                        )
                        storage.add_user_group_access(access)
                        storage._save_data()
                        logger.info(f"已保存用户 {user.username} 的群组 {group.group_name} 访问记录")
            except Exception as e:
                logger.error(f"检查用户 {user_id} 在群组 {group.group_name} 的状态时出错: {str(e)}")
                continue
        
        # 记录找到的群组数量
        logger.info(f"用户 {user.username} 共在 {len(user_groups)} 个群组中")
        
        # 构建群组信息文本
        groups_text = "无" if not user_groups else "\n".join([f"• {group.group_name}" for group in user_groups])
        
        # 构建用户信息文本
        info_text = f"""
<b>👤 个人信息</b>

<b>基本信息</b>
• 用户名：{user.username}
• 注册时间：{user.join_date.strftime('%Y-%m-%d')}

<b>积分状态</b>
• 当前积分：<b>{format_number(user.points)}</b> 积分
• 冻结积分：{format_number(user.frozen_points)} 积分

<b>签到记录</b>
• 连续签到：<b>{format_number(user.streak_days)}</b> 天
• 历史最长：{format_number(user.max_streak_days)} 天
• 本月签到：{format_number(user.monthly_checkins)} 次
• 总签到数：{format_number(user.total_checkins)} 次
• 补签机会：{format_number(user.makeup_chances)} 次

<b>账号绑定</b>
• 邮箱：{user.email or '未绑定'} 
• 验证状态：{'✅ 已验证' if user.email_verified else '❌ 未验证'}

<b>权益群组</b>
{groups_text}
"""
        
        # 创建快捷操作按钮
        keyboard = [
            [
                InlineKeyboardButton("📝 每日签到", callback_data="checkin"),
                InlineKeyboardButton("🏆 查看排行", callback_data="leaderboard_points")
            ],
            [
                InlineKeyboardButton("📧 绑定邮箱", callback_data="bindemail"),
                InlineKeyboardButton("🔄 刷新信息", callback_data="myinfo")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 更新加载消息
        await loading_message.edit_text(
            info_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        # 在命令执行完成后打印汇总信息
        logger.info(f"my_info_command 执行完成，用户 {user.username} 的群组权限检查结果：{len(user_groups)} 个群组")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    全局错误处理函数
    
    处理机器人运行过程中出现的各种异常，记录错误信息并向用户提供友好的错误提示
    
    Args:
        update: Telegram更新对象
        context: 上下文对象，包含错误信息
    """
    # 获取错误信息
    error = context.error
    
    # 记录错误日志
    if update:
        logger.error(f"处理更新 {update.update_id} 时出错", exc_info=error)
    else:
        logger.error("处理未知更新时出错", exc_info=error)
    
    # 对不同类型的错误进行处理
    error_message = "❌ 发生错误，请稍后再试"
    
    # 网络相关错误
    if "NetworkError" in str(error) or "TelegramError" in str(error):
        error_message = "❌ 网络连接错误，请检查您的网络连接或稍后再试"
    
    # 权限相关错误
    elif "Forbidden" in str(error) or "权限不足" in str(error):
        error_message = "❌ 权限不足，机器人无法执行此操作"
    
    # 命令格式错误
    elif "Bad Request" in str(error) or "格式错误" in str(error):
        error_message = "❌ 命令格式错误，请检查您的输入"
    
    # 超时错误
    elif "Timeout" in str(error) or "超时" in str(error):
        error_message = "❌ 操作超时，请稍后再试"
        
    # 如果有消息更新对象，回复错误提示
    if update and update.effective_message:
        try:
            # 尝试发送错误消息
            await update.effective_message.reply_text(
                error_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            # 如果发送错误消息也失败了，记录这个新错误
            logger.error(f"发送错误消息时出错: {e}")
    
    # 向开发者发送详细错误报告（可选）
    # 只有在配置了ADMIN_IDS且列表不为空时才发送
    if hasattr(config, 'ADMIN_IDS') and config.ADMIN_IDS:
        try:
            # 向第一个管理员发送错误报告
            admin_id = config.ADMIN_IDS[0]
            error_text = f"""
<b>⚠️ 机器人错误报告</b>

<b>时间</b>: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>错误类型</b>: {type(error).__name__}
<b>错误信息</b>: {str(error)}

<b>更新信息</b>:
{update.to_json() if update else '无更新信息'}
"""
            # 向管理员发送错误报告
            await context.bot.send_message(
                chat_id=admin_id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"向管理员发送错误报告时出错: {e}")
            
    return

async def handle_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    @description: 处理按钮回调
    @param {Update} update: Telegram更新对象
    @param {ContextTypes.DEFAULT_TYPE} context: 上下文对象
    """
    query = update.callback_query
    try:
        logger.info(f"收到按钮回调，用户: {query.from_user.username} (ID: {query.from_user.id}), 数据: {query.data}")
        
        # 调试信息：更详细地输出回调信息
        logger.debug(f"按钮回调详情 - 消息ID: {query.message.message_id if query.message else 'None'}, "
                    f"聊天ID: {query.message.chat.id if query.message else 'None'}, "
                    f"回调ID: {query.id}, 数据: {query.data}")
        
        # 检查是否是其他模块应该处理的回调，如果是则直接返回
        # 注意：这里列出的模式都应该由各自的模块处理而不是这个通用处理器
        skip_patterns = [
            "confirm_recovery_", "approve_recovery_", "reject_recovery_", "request_more_info_",
            "admin_", "points_", "accept_", "reject_", "confirm_", "cancel_"
        ]
        
        for pattern in skip_patterns:
            if query.data.startswith(pattern):
                logger.debug(f"按钮回调 {query.data} 应由专门的处理器处理，跳过通用处理")
                return
        
        if query.data == "checkin":
            # 触发签到流程
            await query.answer("正在进行签到...")
            
            # 创建一个新的update对象，使用callback_query来构造
            new_update = Update(
                update_id=update.update_id,
                message=query.message
            )
            
            # 从handlers模块导入签到处理函数
            from coser_bot.handlers.checkin import process_checkin
            
            # 调用签到函数
            result = await process_checkin(new_update, context)
            
            await query.message.reply_text(
                result,
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_keyboard()
            )
        
        elif query.data == "myinfo":
            # 模拟执行 /myinfo 命令
            await query.answer("正在加载个人信息...")
            
            # 直接使用query.from_user而不是尝试设置message.from_user
            await my_info_command(update, context)
        
        elif query.data == "help":
            # 模拟执行 /help 命令
            await query.answer("正在显示帮助信息...")
            
            # 直接使用query.from_user
            await help_command(update, context)
        
        elif query.data == "bindemail":
            # 模拟执行 /bindemail 命令
            await query.answer("正在准备邮箱绑定...")
            
            # 从模块中导入bind_email_command函数
            from coser_bot.handlers.email import bind_email_command
            
            # 创建一个临时消息对象，使用回调查询消息的信息
            class TempMessage:
                def __init__(self, message):
                    self.chat_id = message.chat_id
                    self.message_id = message.message_id
                    self.from_user = query.from_user
                    self.chat = message.chat
                
                async def reply_text(self, text, **kwargs):
                    return await query.message.reply_text(text, **kwargs)
            
            # 创建一个新的Update对象，使用临时消息
            temp_message = TempMessage(query.message)
            temp_update = Update(update_id=update.update_id, message=temp_message)
            
            # 调用bind_email_command函数
            await bind_email_command(temp_update, context)
        
        elif query.data == "points":
            # 查询积分
            await query.answer("正在查询积分信息...")
            
            # 从handlers模块导入积分查询函数
            from coser_bot.handlers.points import get_user_points_info
            
            # 获取积分信息
            result = await get_user_points_info(query.from_user.id)
            
            # 回复查询结果
            await query.message.reply_text(
                result,
                parse_mode=ParseMode.HTML
            )
        
        elif query.data.startswith("leaderboard_"):
            # 交给排行榜处理器处理
            await handle_leaderboard_callback(update, context)
            
        elif query.data == "daily_tasks":
            # 显示每日任务
            await query.answer("正在加载每日任务...")
            
            # 获取用户信息
            storage = Storage()
            user = storage.get_user(query.from_user.id)
            
            # 构建每日任务信息
            has_checked_in = user.last_checkin and user.last_checkin.date() == datetime.now().date()
            
            tasks_text = f"""
<b>✅ 每日任务中心</b>

完成以下任务可获得积分奖励：

1. 每日签到: {("已完成 ✓" if has_checked_in else "未完成 ✗")} [+10积分]
2. 绑定邮箱: {("已完成 ✓" if user.email and user.email_verified else "未完成 ✗")} [+50积分]
3. 邀请好友: 已邀请 {user.invited_users if hasattr(user, 'invited_users') else 0} 人 [每人+30积分]

<b>🔄 每周任务</b>
1. 连续签到7天: {f"进度 {user.checkin_streak if hasattr(user, 'checkin_streak') else 0}/7"} [+50积分]
2. 累计登录30天: {f"进度 {user.login_days if hasattr(user, 'login_days') else 0}/30"} [+100积分]

完成任务不仅可以获得积分，还能解锁更多社群特权！
"""
            await query.message.reply_text(
                tasks_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_keyboard()
            )
            
        # 注意: 积分商城功能已被移除，因为该功能尚未实现
        # 相关的按钮和处理代码已删除
            
        elif query.data == "invite_friends":
            # 邀请好友功能
            await query.answer("此功能暂未实现")
            
            # 注意：邀请好友功能尚未完全实现，仅保留界面元素
            # 原代码已被注释掉
            """
            原邀请文本：
            
            <b>👥 邀请好友</b>

            每邀请一位新用户加入社群，您将获得<b>30积分</b>奖励！

            <b>邀请方式：</b>
            1. 将机器人分享给您的好友
            2. 让好友发送 /start 命令
            3. 好友成功注册后，您将自动获得奖励

            <b>邀请优势：</b>
            • 邀请人数越多，奖励越丰厚
            • 特定活动期间邀请好友可获得双倍奖励
            • 邀请10位以上好友可获得专属徽章

            <i>注：每个用户只能被邀请一次，重复邀请不计入奖励</i>
            """
            
            # 简化的提示信息，告知用户功能未实现
            await query.message.reply_text(
                "<b>👥 邀请好友</b>\n\n此功能正在开发中，即将上线。",
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_keyboard()
            )
        
        else:
            await query.answer("未知的操作")
            
    except Exception as e:
        logger.error(f"处理按钮回调时出错: {e}", exc_info=True)
        await query.answer("❌ 操作失败，请稍后重试")

def main() -> None:
    """
    机器人主函数
    
    初始化并启动机器人，注册所有命令处理器，设置定时任务
    """
    # 清理Telegram API会话文件
    try:
        # 清理python-telegram-bot库的会话文件
        home_dir = os.path.expanduser("~")
        # 尝试不同可能的会话目录
        session_dirs = [
            os.path.join(home_dir, ".telegram-bot-api"),  # 标准目录
            os.path.join(home_dir, ".cache", "python-telegram-bot"),  # Linux/Mac缓存目录
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "python-telegram-bot")  # Windows应用数据目录
        ]
        
        for session_dir in session_dirs:
            if os.path.exists(session_dir):
                try:
                    shutil.rmtree(session_dir)
                    logger.info(f"已清理Telegram API会话目录: {session_dir}")
                except:
                    logger.warning(f"无法清理会话目录: {session_dir}")
    except Exception as e:
        logger.warning(f"清理会话文件时出错: {e}")
    
    # 实例锁，防止多个实例同时运行
    lock_file = os.path.join(tempfile.gettempdir(), "coser_bot.lock")
    
    # 检查锁文件是否过时（超过1小时）
    if os.path.exists(lock_file):
        file_age = time.time() - os.path.getmtime(lock_file)
        if file_age > 3600:  # 1小时 = 3600秒
            try:
                os.remove(lock_file)
                logger.warning(f"删除过期的锁文件（{int(file_age/60)}分钟）")
            except:
                pass
    
    try:
        # 尝试创建锁文件
        if os.path.exists(lock_file):
            # 检查锁文件中的PID是否还在运行
            try:
                with open(lock_file, 'r') as f:
                    old_pid = int(f.read().strip())
                
                # 检查进程是否存在
                is_running = False
                
                # 针对Windows系统的检查
                if platform.system() == "Windows":
                    try:
                        import psutil
                        is_running = psutil.pid_exists(old_pid)
                    except ImportError:
                        # 如果没有psutil，则使用Windows API
                        try:
                            kernel32 = ctypes.windll.kernel32
                            PROCESS_QUERY_INFORMATION = 0x0400
                            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, old_pid)
                            if handle != 0:
                                is_running = True
                                kernel32.CloseHandle(handle)
                        except:
                            # 如果API调用失败，为安全起见，假定进程在运行
                            is_running = True
                else:
                    # 在Unix系统上检查进程
                    try:
                        os.kill(old_pid, 0)
                        is_running = True
                    except OSError:
                        is_running = False
                
                if is_running:
                    logger.error(f"另一个机器人实例(PID: {old_pid})已在运行！请先关闭该实例。")
                    print(f"❌ 错误：另一个机器人实例(PID: {old_pid})已在运行！请先关闭该实例。")
                    sys.exit(1)
                else:
                    # 进程不存在，可能是之前的实例异常退出
                    logger.warning(f"发现之前的锁文件，但进程似乎已经结束。继续启动...")
                    # 删除旧的锁文件
                    try:
                        os.remove(lock_file)
                    except:
                        pass
            except Exception as e:
                # 锁文件读取失败，可能已损坏
                logger.warning(f"锁文件读取失败，可能已损坏。删除并继续... 错误: {e}")
                try:
                    os.remove(lock_file)
                except:
                    pass
        
        # 创建新的锁文件
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # 注册退出时删除锁文件
        def cleanup_lock():
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    logger.info("已删除锁文件")
            except Exception as e:
                logger.error(f"删除锁文件时出错: {e}")
                pass
        
        atexit.register(cleanup_lock)
        
        # 检查机器人令牌
        if not config.BOT_TOKEN:
            logger.error("未设置BOT_TOKEN环境变量")
            sys.exit(1)
        
        # 创建应用
        # 设置更长的连接超时时间
        request = HTTPXRequest(connection_pool_size=8, read_timeout=30.0, write_timeout=30.0, connect_timeout=30.0)
        application = Application.builder().token(config.BOT_TOKEN).request(request).build()
        
        # 初始化存储对象并添加到application.bot_data中
        from coser_bot.database.storage import Storage
        storage_obj = Storage()
        application.bot_data["storage"] = storage_obj
        logger.info("存储对象已初始化并添加到application.bot_data中")
        
        # 注册处理器
        # 基本命令
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("myinfo", my_info_command))
        
        # 健康检查相关处理器
        from coser_bot.utils.health_check import get_health_check_handlers
        for handler in get_health_check_handlers():
            application.add_handler(handler)
        
        # 恢复请求相关处理器 - 确保这些处理器最先注册，以便它们有最高优先级
        for handler in get_recovery_handlers():
            application.add_handler(handler)
            
        # 管理员相关处理器
        for handler in get_admin_handlers():
            application.add_handler(handler)
            
        # 签到相关处理器
        for handler in get_checkin_handlers():
            application.add_handler(handler)
        
        # 积分相关处理器
        for handler in get_points_handlers():
            application.add_handler(handler)
        
        # 邮箱相关处理器
        for handler in get_email_handlers():
            application.add_handler(handler)
        
        # 排行榜相关处理器
        for handler in get_leaderboard_handlers():
            application.add_handler(handler)
            
        # 群组同步相关处理器
        for handler in get_group_sync_handlers():
            application.add_handler(handler)
            
        # 通用按钮回调处理器 - 应该最后注册，以便它只处理其他处理器未处理的回调
        application.add_handler(CallbackQueryHandler(handle_button_callback))
        
        # 添加文本消息处理器，处理特定关键词
        from coser_bot.handlers.points import points_command
        from coser_bot.handlers.leaderboard import show_leaderboard
        
        # 处理"积分"关键词 - 使用更简单的过滤器
        application.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r"^积分$"), 
            lambda update, context: points_command(update, context)
        ))
        
        # 处理"积分排行"关键词 - 使用更简单的过滤器
        application.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r"^积分排行$"), 
            lambda update, context: show_leaderboard(update, context)
        ))
        
        # 添加定时任务
        job_queue = application.job_queue
        # 每6小时同步一次群组成员
        job_queue.run_repeating(sync_group_members, interval=21600)
        
        # 添加数据库备份定时任务
        from coser_bot.utils.backup import schedule_backup
        # 每24小时备份一次数据库
        job_queue.run_repeating(schedule_backup, interval=86400)
        
        # 添加日志清理定时任务
        from coser_bot.utils.log_manager import schedule_log_cleanup
        # 每7天清理一次日志
        job_queue.run_repeating(schedule_log_cleanup, interval=604800)
        
        # 添加错误处理器
        application.add_error_handler(error_handler)
        
        # 解决getUpdates冲突问题
        try:
            # 在启动前，尝试重置更新状态
            import httpx
            import json
            bot_token = config.BOT_TOKEN
            
            # 首先尝试获取更新ID，找出最大值
            offset = 0
            try:
                with httpx.Client(timeout=30.0) as client:  # 增加超时时间到30秒
                    response = client.post(
                        f"https://api.telegram.org/bot{bot_token}/getUpdates",
                        data={"timeout": 1}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data["ok"] and data["result"]:
                            # 找出最大的更新ID
                            max_update_id = max(update["update_id"] for update in data["result"])
                            # 设置偏移量为最大更新ID+1，这样会清除所有旧的更新
                            offset = max_update_id + 1
                            logger.info(f"找到待处理的更新，设置偏移量为 {offset} 以清除旧更新")
            except Exception as e:
                logger.warning(f"获取更新ID失败: {e}")
            
            # 如果无法获取更新ID或没有找到更新，使用强制清除方法
            if offset == 0:
                offset = 999999999  # 使用一个非常大的数字作为偏移量
                logger.info("使用强制清除方法重置更新状态")
            
            # 执行一次getUpdates请求，使用上面确定的偏移量，这会清除所有旧的更新
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(
                        f"https://api.telegram.org/bot{bot_token}/getUpdates",
                        data={"offset": offset, "timeout": 1}
                    )
                    if response.status_code == 200:
                        logger.info("更新状态重置成功")
                    else:
                        logger.warning(f"更新状态重置失败: {response.status_code} {response.text}")
            except Exception as e:
                logger.warning(f"重置更新状态失败: {e}")
            
            # 确保与Telegram API服务器的连接正常
            time.sleep(2)  # 等待一段时间，确保连接完全关闭
            
        except Exception as e:
            logger.warning(f"尝试解决getUpdates冲突失败: {e}")
        
        # 原来的初始化代码
        logger.info("启动Coser社群机器人...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"启动机器人时发生错误: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()