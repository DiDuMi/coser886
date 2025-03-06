"""
@description: 常量配置模块，存储系统中使用的常量和模板
"""
from enum import Enum, auto

# 消息类型
class MessageType(Enum):
    PRIVATE = auto()
    GROUP = auto()
    TOPIC = auto()

# 用户角色
class UserRole(Enum):
    ADMIN = auto()
    MEMBER = auto()
    GUEST = auto()

# 积分交易类型
class PointsTransactionType(Enum):
    CHECKIN = "签到"
    STREAK_BONUS = "连续签到奖励"
    GIFT_SENT = "赠送积分"
    GIFT_RECEIVED = "收到积分"
    ADMIN_ADJUSTMENT = "管理员调整"
    EMAIL_VERIFICATION = "邮箱验证奖励"

# 邮箱验证状态
class EmailVerifyStatus(Enum):
    PENDING = "待验证"
    VERIFIED = "已验证"
    EXPIRED = "已过期"

# 命令列表
COMMANDS = {
    "start": "开始使用机器人",
    "help": "获取帮助信息",
    "checkin": "每日签到",
    "points": "查询积分",
    "gift": "赠送积分",
    "bindemail": "绑定邮箱",
    "verify": "验证邮箱",
    "recover": "账号权益恢复",
    "leaderboard": "查看排行榜",
    "rank": "查看排行榜"
}

# 回复模板
TEMPLATES = {
    "checkin_success": """
✅ <b>签到成功!</b>

👤 用户：{username}
📅 日期：{date}
🔢 连续签到：{streak_days}天
💰 获得积分：{points}
💎 当前积分：{total_points}

明天再来签到获取更多积分吧~
""",
    "checkin_streak_bonus": """
🎉 签到成功！
👤 用户：{username}
💰 基础积分：{base_points}
🎁 连续签到{streak_days}天奖励：+{bonus_points}
📈 当前积分：{total_points}
📆 连续签到：{streak_days}天
🎯 下次额外奖励：还需{days_to_next_reward}天(+{next_reward_points}积分)
""",
    "checkin_monthly_bonus": """
🌟 签到成功！
👤 用户：{username}
💰 基础积分：{base_points}
🏆 连续签到30天奖励：+{bonus_points}
📈 当前积分：{total_points}
📆 连续签到：{streak_days}天
✨ 太棒了！你已经连续签到一个月啦！
""",
    "checkin_already": """
⚠️ 今天已经签到过啦！
📅 明天再来吧~
""",
    "gift_success": """
🎁 <b>积分赠送成功!</b>

👤 赠送者：{sender_username}
👥 接收者：{receiver_username}
💰 赠送积分：{amount}
💬 赠送备注：{reason}
💎 你的剩余积分：{sender_points}

感谢你的慷慨!
""",
    "email_verification_sent": """
📧 验证邮件已发送！
👤 用户：@{username}
📩 邮箱：{email}
⏱️ 有效期：{expiry}分钟
请查收邮件并使用 /verify 命令验证
""",
    "verification_sent": """
📧 <b>验证邮件已发送!</b>

📩 邮箱：{email}
⏱️ 验证码有效期：{expiry_minutes}分钟

请查收邮件并输入收到的验证码。
""",
    "help": """
🤖 <b>Coser社群机器人使用帮助</b>

<b>基础命令：</b>
/start - 开始使用机器人
/help - 显示帮助信息
/checkin - 每日签到领取积分
/stats - 查看签到统计信息
/points - 查看积分余额和明细
/makeup - 使用积分进行补签
/leaderboard - 查看排行榜
/rank - 查看排行榜(简写)

<b>积分相关：</b>
- 每日签到可获得 {daily_points} 积分
- 连续签到7天可额外获得 {weekly_points} 积分
- 连续签到30天可额外获得 {monthly_points} 积分
- 每月有 {makeup_chances} 次补签机会，每次补签消耗 {makeup_cost} 积分

<b>邮箱验证：</b>
/verify - 验证邮箱，获取更多权限

<b>群组功能：</b>
- 在群组中发送"签到"也可以完成签到
- 管理员可使用 /admin 查看管理命令

如需帮助，请联系管理员。
""",
    "welcome": """
👋 <b>欢迎使用Coser社群机器人!</b>

这是一个为Coser社群设计的多功能机器人，可以帮助你:
- 每日签到获取积分
- 管理和使用积分
- 更多功能正在开发中...

发送 /help 查看所有可用命令。
""",
    "checkin_success": """
✅ <b>签到成功!</b>

👤 用户：{username}
📅 日期：{date}
🔢 连续签到：{streak_days}天
💰 获得积分：{points}
💎 当前积分：{total_points}

明天再来签到获取更多积分吧~
""",
    "checkin_streak_bonus": """
🎉 <b>连续签到奖励!</b>

👤 用户：{username}
📅 日期：{date}
🔢 连续签到：{streak_days}天
💰 基础积分：{base_points}
✨ 额外奖励：{bonus_points}
💎 当前积分：{total_points}

恭喜你获得连续签到奖励! 继续保持签到习惯吧~
""",
    "checkin_monthly_bonus": """
🏆 <b>月度签到达成!</b>

👤 用户：{username}
📅 日期：{date}
🔢 连续签到：{streak_days}天
💰 基础积分：{base_points}
🌟 月度奖励：{monthly_bonus}
💎 当前积分：{total_points}

太棒了! 你已经连续签到一个月，获得了丰厚奖励!
""",
    "checkin_already": """
ℹ️ <b>今日已签到</b>

你今天已经签到过了，明天再来吧~
当前积分: {points}
连续签到: {streak_days}天
""",
    "gift_request": """
🎁 <b>积分赠送请求</b>

👤 赠送者：{sender_username}
💰 赠送积分：{amount}
💬 赠送备注：{reason}

请在{expiry_hours}小时内接受或拒绝这份礼物。
""",
    "gift_confirm_request": """
🎁 <b>积分赠送确认</b>

您即将赠送积分：
👥 接收者：{receiver_username}
💰 赠送积分：{amount}
💬 赠送备注：{reason}
💎 您当前积分：{sender_points}

请确认是否继续？
""",
    "gift_canceled": """
❌ <b>积分赠送已取消</b>

您已取消向 {receiver_username} 赠送 {amount} 积分的操作。
""",
    "gift_accepted": """
✅ <b>积分赠送已接受!</b>

👤 赠送者：{sender_username}
👥 接收者：{receiver_username}
💰 赠送积分：{amount}
💬 赠送备注：{reason}
💎 你的当前积分：{receiver_points}

感谢这份礼物!
""",
    "gift_rejected": """
❌ <b>积分赠送已拒绝</b>

👤 赠送者：{sender_username}
👥 接收者：{receiver_username}
💰 赠送积分：{amount}
💬 赠送备注：{reason}

积分已退还给赠送者。
""",
    "gift_received": """
🎁 <b>您已成功接收积分!</b>

👤 赠送者：{sender_username}
💰 收到积分：{amount}
💬 赠送备注：{reason}
💎 您当前积分：{receiver_points}

感谢这份礼物!
""",
    "gift_expired": """
⏰ <b>积分赠送已过期</b>

👤 赠送者：{sender_username}
👥 接收者：{receiver_username}
💰 赠送积分：{amount}
💬 赠送备注：{reason}

由于接收者未在{expiry_hours}小时内响应，积分已退还给赠送者。
""",
    "insufficient_points": """
❗ <b>积分不足</b>

你当前的积分余额为{current_points}，无法赠送{amount}积分。
""",
    "points_query": """
💰 <b>积分账户详情</b>

👤 用户：{username}
💎 <b>当前积分：{points}</b>

📊 <b>积分统计</b>
┣ 📈 累计获得：{total_earned}
┣ 🎁 累计赠送：{total_gifted}
┗ 🎯 累计接收：{total_received}

📈 <b>积分使用情况</b>
{points_chart}

📋 <b>最近交易记录</b>
{recent_transactions}

💡 <i>继续签到和参与社群活动可以获得更多积分哦!</i>
""",
    "checkin_stats": """
📊 <b>签到统计</b>

👤 用户：{username}
📅 首次签到：{first_checkin}
🔢 连续签到：{current_streak}天
🏆 最长连续：{max_streak}天
📈 总签到次数：{total_checkins}次
📉 错过签到：{missed_days}天

继续保持签到习惯吧!
""",
    "email_binding_start": """
📧 <b>邮箱绑定</b>

请输入您要绑定的邮箱地址：
例如：example@domain.com

<i>邮箱将用于账号权益恢复，请确保输入正确的邮箱地址。</i>
""",
    "email_verification_sent": """
📧 <b>验证码已发送</b>

验证码已发送至 <code>{email}</code>
有效期：{expiry_minutes}分钟

请输入收到的6位数验证码：
""",
    "email_binding_success": """
✅ <b>邮箱绑定成功！</b>

您已成功绑定邮箱：<code>{email}</code>
此邮箱将用于账号权益恢复，请妥善保管。{bonus_text}

当前积分：{points}
""",
    "email_binding_failed": """
❌ <b>邮箱绑定失败</b>

原因：{reason}

您可以使用 /bindemail 命令重新尝试绑定邮箱。
""",
    "email_verification_expired": """
⏰ <b>验证码已过期</b>

您的验证码已过期，请重新开始邮箱绑定流程。

使用 /bindemail 命令重新开始。
""",
    "email_verification_failed": """
⚠️ <b>验证失败</b>

验证码错误，请重新输入。
剩余尝试次数：{attempts_left}
""",
    "email_binding_prompt": """
📧 <b>邮箱绑定</b>

请输入您要绑定的邮箱地址：
例如：example@example.com

您可以随时发送 /cancel 取消操作。
""",
    "email_verification_prompt": """
🔑 <b>邮箱验证</b>

请输入您收到的验证码：
例如：123456

您可以随时发送 /cancel 取消操作。
""",
    "email_already_bound": """
📌 <b>邮箱已绑定</b>

您当前已绑定邮箱：{email}

是否要更换绑定的邮箱？
""",
    "email_binding_insufficient_points": """
⚠️ <b>积分不足</b>

绑定邮箱需要至少 {required_points} 积分。
您当前积分：{current_points}

请继续签到或参与活动获取更多积分。
""",
    "email_invalid_format": """
❌ <b>邮箱格式错误</b>

您输入的邮箱格式不正确，请重新输入有效的邮箱地址。
例如：example@example.com
""",
    "email_already_used": """
⚠️ <b>邮箱已被使用</b>

该邮箱已被其他用户绑定，请使用其他邮箱地址。
""",
    "email_verification_error": """
❌ <b>验证错误</b>

创建验证请求时出现错误，请稍后重试。
""",
    "email_send_failed": """
❌ <b>邮件发送失败</b>

发送验证邮件时出现错误，请检查邮箱地址是否正确或稍后重试。
""",
    "email_verification_sent": """
📤 <b>验证邮件已发送</b>

验证邮件已发送至：{email}
请在 {expiry_minutes} 分钟内完成验证。

您可以通过 /verify_email 命令输入验证码。
""",
    "email_verification_invalid": """
❌ <b>验证码无效</b>

您输入的验证码不正确，请重新输入。
""",
    "email_verification_expired": """
⏱️ <b>验证码已过期</b>

您的验证码已过期，请重新发起邮箱绑定请求。
""",
    "user_not_found": """
❓ <b>用户不存在</b>

未找到您的用户信息，请联系管理员。
""",
    "email_verification_success": """
✅ <b>邮箱验证成功</b>

您的邮箱 {email} 已成功绑定到您的账号。
现在您可以在需要时通过邮箱恢复账号权益。

💰 当前积分：{points} 分
""",
    "email_unchanged": """
ℹ️ <b>邮箱未变更</b>

您的邮箱保持不变：<code>{email}</code>
""",
    "email_change_cooldown": """
⏳ <b>邮箱更改冷却中</b>

您最近已更改过邮箱，需等待 {days_left} 天后才能再次更改。
""",
    "operation_cancelled": """
🚫 <b>操作已取消</b>

您已取消当前操作。
""",
    "points_transfer_message": """
💸 <b>积分转账</b>

您已成功向 {recipient} 转账 {amount} 积分。

当前积分余额：{balance}
交易编号：{transaction_id}
""",
    "recovery_start": """
🔄 <b>账号权益恢复</b>

欢迎使用账号权益恢复功能。此功能可以帮助您在原账号被封禁时，将权益转移到新账号。

<i>请按照提示完成验证流程。</i>
""",
    "recovery_email_prompt": """
📧 <b>请输入原账号绑定的邮箱</b>

请输入您原账号绑定的邮箱地址。
""",
    "recovery_email_not_found": """
❌ <b>邮箱未找到</b>

系统中没有找到使用该邮箱绑定的账号，请检查邮箱地址是否正确。
""",
    "recovery_same_account": """
ℹ️ <b>相同账号</b>

您输入的邮箱绑定的就是当前账号，无需进行恢复操作。
""",
    "recovery_verification_sent": """
📤 <b>验证码已发送</b>

验证码已发送至 <code>{email}</code>
请在 {expiry_minutes} 分钟内输入收到的6位数验证码。

<i>如未收到邮件，请检查垃圾邮件箱。</i>
""",
    "recovery_account_info": """
📋 <b>原账号信息</b>

验证成功！您的原账号信息如下：

👤 用户名：@{username}
📅 注册时间：{join_date}
💰 积分余额：{points} 分
🏢 所属群组/频道：
{group_info}

请点击下方按钮申请恢复权益。
""",
    "recovery_reason_prompt": """
📝 <b>请说明申请原因</b>

请简要说明您的账号被封禁原因（50字以内）。
""",
    "recovery_reason_too_long": """
❌ <b>内容过长</b>

您输入的原因超过50字，请精简后重新提交。
""",
    "recovery_request_submitted": """
✅ <b>申请已提交</b>

您的恢复申请已提交，申请编号：<code>{request_id}</code>

请耐心等待管理员审核，审核结果将通过Bot通知您。
审核通常在1-3个工作日内完成。
""",
    "recovery_request_failed": """
❌ <b>申请提交失败</b>

恢复申请提交失败，请稍后重试或联系管理员。
""",
    "recovery_session_expired": """
⏱️ <b>会话已过期</b>

您的恢复会话已过期，请重新发起恢复流程。
""",
    "recovery_request_exists": """
ℹ️ <b>申请已存在</b>

您已有一个正在处理的恢复申请（编号：<code>{request_id}</code>），
请等待管理员审核，或等待 {days_left} 天后再次申请。
""",
    "recovery_approved": """
🎉 <b>恭喜！您的权益恢复申请已通过</b>

以下是您的群组邀请链接：
{group_links}

请在24小时内使用这些链接加入群组/频道。
加入后您的权益将自动恢复。
""",
    "recovery_rejected": """
❌ <b>申请被拒绝</b>

很抱歉，您的权益恢复申请未通过审核。
如有疑问，请联系管理员。
""",
    "recovery_request_not_found": """
❓ <b>申请未找到</b>

未找到指定的恢复申请，可能已被处理或已过期。
""",
    "admin_recovery_notification": """
🔔 <b>新权益恢复申请 #{request_id}</b>

<b>原账号信息：</b>
👤 用户名：@{old_username}
🆔 用户ID：{old_user_id}
📅 注册时间：{join_date}
💰 积分余额：{points} 分

<b>新账号信息：</b>
👤 用户名：@{new_username}
🆔 用户ID：{new_user_id}

<b>申请原因：</b>
{reason}

<b>所属群组/频道：</b>
{group_info}
""",
    "admin_recovery_approved": """
✅ <b>恢复申请已批准</b>

申请编号：<code>{request_id}</code>
处理管理员：@{admin_username}

已生成邀请链接并通知用户。
""",
    "admin_recovery_rejected": """
❌ <b>恢复申请已拒绝</b>

申请编号：<code>{request_id}</code>
处理管理员：@{admin_username}

已通知用户申请被拒绝。
""",
    "admin_request_more_info_prompt": """
❓ <b>请输入需要补充的信息</b>

请输入您希望用户补充的信息（针对申请 <code>{request_id}</code>）：
""",
    "user_info": """
👤 <b>用户信息</b>

📋 用户名：@{username}
🆔 用户ID：{user_id}
📅 加入时间：{join_date}
💰 当前积分：{points}
📊 连续签到：{streak_days}天
✉️ 邮箱状态：{email_status}
🏅 权益群组：{groups}

累计数据：
📝 总签到次数：{total_checkins}
🎁 收到礼物：{received_gifts}
💝 发出礼物：{sent_gifts}
""",
    "points_info": """
👋 欢迎 {username}！
💰 当前积分：<code>{points}</code>
❄️ 冻结积分：<code>{frozen_points}</code>

请选择要查看的内容：
""",
    "points_overview": """
📊 <b>积分概览</b>

👤 用户：{username}
💰 当前积分：<code>{points}</code>
❄️ 冻结积分：<code>{frozen_points}</code>
📝 总签到次数：<code>{total_checkins}</code>
📅 本月签到：<code>{monthly_checkins}</code>
🔄 连续签到：<code>{streak_days}</code>天
""",
    "points_stats": """
📊 <b>积分统计</b>

👤 用户：{username}
🔄 当前连续签到：<code>{streak_days}</code>天
🏆 最长连续签到：<code>{max_streak_days}</code>天
📝 总签到次数：<code>{total_checkins}</code>
📅 本月签到次数：<code>{monthly_checkins}</code>
""",
    "leaderboard_points": """
🏆 <b>积分排行榜 TOP 10</b>

{rankings}

更新时间: {update_time}
""",
    "leaderboard_streak": """
🔥 <b>连续签到排行榜 TOP 10</b>

{rankings}

更新时间: {update_time}
""",
    "leaderboard_monthly": """
📅 <b>本月签到排行榜 TOP 10</b>

{rankings}

更新时间: {update_time}
""",
    "leaderboard_empty": """
📊 <b>{title}</b>

暂无数据

更新时间: {update_time}
""",
    "welcome_message": """
👋 欢迎使用 <b>Coser社群机器人</b>！

这是你的个人助手，帮助你管理积分、查看群组权益和参与社群活动。

<b>🔑 快速开始</b>
• 每日签到: 领取积分
• 查看信息: 了解你的积分和权益
• 绑定邮箱: 保障账号安全

请使用下方按钮开始体验。

<b>需要帮助?</b> 点击 "帮助指南" 查看详细使用说明。
""",
    "help_message": """
📖 <b>Coser社群机器人使用指南</b>

<b>🎯 基础功能</b>
• /start - 显示欢迎信息
• /help - 查看此帮助指南
• /myinfo - 查看个人详细信息

<b>💰 积分系统</b>
• /checkin - 每日签到领积分
• /points - 查看积分余额
• /rank - 查看排行榜
• /gift - 赠送积分，使用方法：
  1️⃣ 回复消息：赠送 数量 [理由]
  2️⃣ 指定用户：赠送 @用户名 数量 [理由]

<b>📧 账号管理</b>
• /bindemail - 绑定邮箱账号
• /recover - 申请权益恢复

<b>⭐️ 积分规则</b>
1️⃣ 签到奖励
   • 每日签到：10 积分
   • 连续7天：额外 30 积分
   • 连续30天：额外 100 积分

2️⃣ 其他奖励
   • 绑定邮箱：50积分
   • 邀请新用户：20积分/人
   • 活动参与：不定期奖励

3️⃣ 积分使用
   • 用于群组权益
   • 可赠送给其他用户

<b>💡 使用技巧</b>
• 坚持每日签到获取更多奖励
• 及时绑定邮箱保障账号安全
• 定期查看积分余额和交易记录
• 注意群组会员的有效期

<b>❓ 遇到问题？</b>
如果你在使用过程中遇到任何问题：
1️⃣ 检查命令输入是否正确
2️⃣ 查看最新的系统公告
3️⃣ 联系运营寻求帮助 @didumibot

🌈 祝你在 Coser 社群玩得开心！
""",
}

# 签到消息模板
CHECKIN_SUCCESS_TEMPLATE = """
✅ <b>签到成功！</b>

👤 用户：{username}
💰 积分：{points}
🎁 获得：+{earned_points}
📆 连续签到：{streak_days} 天

🔜 再连续签到可获得{next_reward}：+{next_reward_points} 积分
"""

CHECKIN_ALREADY_TEMPLATE = """
⚠️ <b>今日已签到</b>

👤 用户：{username}
💰 积分：{points}
📆 连续签到：{streak_days} 天

🔜 明天签到可获得{next_reward}：+{next_reward_points} 积分
"""

CHECKIN_STREAK_TEMPLATE = """
🔄 <b>连续签到成功！</b>

👤 用户：{username}
💰 积分：{points}
🎁 获得：+{earned_points}
📆 连续签到：{streak_days} 天

🔜 再连续签到可获得{next_reward}：+{next_reward_points} 积分
"""

CHECKIN_WEEKLY_BONUS_TEMPLATE = """
🎉 <b>连续签到一周，获得额外奖励！</b>

👤 用户：{username}
💰 积分：{points}
🎁 基础奖励：+{earned_points}
🎖️ 连续签到奖励：+{bonus_points}
📊 总计获得：+{total_points}
📆 连续签到：{streak_days} 天

🎯 继续保持，下一个大奖等着你！
"""

CHECKIN_MONTHLY_BONUS_TEMPLATE = """
🌟 <b>连续签到一个月，获得丰厚奖励！</b>

👤 用户：{username}
💰 积分：{points}
🎁 基础奖励：+{earned_points}
🏆 月度连续签到奖励：+{bonus_points}
📊 总计获得：+{total_points}
📆 连续签到：{streak_days} 天

👏 恭喜你达成月度签到成就！
"""

# 帮助消息模板
HELP_MESSAGE = """
🤖 <b>Coser社群机器人使用帮助</b>

<b>基础命令：</b>
/start - 开始使用机器人
/help - 显示帮助信息
/checkin - 每日签到领取积分
/stats - 查看签到统计信息
/points - 查看积分余额和明细
/makeup - 使用积分进行补签

<b>积分相关：</b>
- 每日签到可获得 {daily_points} 积分
- 连续签到7天可额外获得 {weekly_points} 积分
- 连续签到30天可额外获得 {monthly_points} 积分
- 每月有 {makeup_chances} 次补签机会，每次补签消耗 {makeup_cost} 积分

<b>邮箱验证：</b>
/verify - 验证邮箱，获取更多权限

<b>群组功能：</b>
- 在群组中发送"签到"也可以完成签到
- 管理员可使用 /admin 查看管理命令

如需帮助，请联系管理员。
"""

# 欢迎消息模板
WELCOME_MESSAGE = """
👋 <b>欢迎使用Coser社群机器人！</b>

我是你的社群助手，可以帮你：
✅ 每日签到获取积分
📊 跟踪你的签到记录和积分
🔐 验证邮箱获取更多权限
🎁 使用积分兑换福利

<b>开始使用：</b>
1. 使用 /checkin 进行每日签到
2. 使用 /help 查看完整功能列表

祝你在社群中玩得开心！
"""

# 管理员帮助消息
ADMIN_HELP_MESSAGE = """
🛠️ <b>管理员命令列表</b>

<b>用户管理：</b>
/admin_points <用户ID> <数量> - 调整用户积分
/admin_list - 列出所有用户
/admin_info <用户ID> - 查看用户详细信息

<b>群组管理：</b>
/admin_group_add - 添加付费群组
/admin_group_remove - 移除付费群组
/admin_group_list - 列出所有群组

<b>系统管理：</b>
/admin_backup - 备份数据
/admin_stats - 查看系统统计信息

请谨慎使用管理员命令。
"""

# 邮箱验证消息
EMAIL_VERIFY_MESSAGE = """
📧 <b>邮箱验证</b>

请使用以下命令验证您的邮箱：
/verify <邮箱地址>

验证邮箱后，您将获得：
✅ 额外的积分奖励
✅ 参与特殊活动的资格
✅ 进入高级群组的权限
"""

EMAIL_VERIFY_SENT_MESSAGE = """
📤 <b>验证邮件已发送</b>

我们已向 {email} 发送了验证邮件。
请查收邮件并点击验证链接，或使用以下命令完成验证：

/confirm {code}

验证码有效期为 {expiry} 分钟。
"""

EMAIL_VERIFY_SUCCESS_MESSAGE = """
✅ <b>邮箱验证成功</b>

恭喜！您的邮箱 {email} 已成功验证。
您已获得 {bonus} 积分奖励！

当前积分：{points}
"""

# 积分交易相关消息
POINTS_TRANSFER_MESSAGE = """
💸 <b>积分转账</b>

您已成功向 {recipient} 转账 {amount} 积分。

当前积分余额：{balance}
交易编号：{transaction_id}
"""

POINTS_RECEIVED_MESSAGE = """
💰 <b>收到积分</b>

您收到来自 {sender} 的 {amount} 积分。

当前积分余额：{balance}
交易编号：{transaction_id}
"""

# 错误消息
ERROR_MESSAGES = {
    "general": "❌ 操作失败，请稍后再试",
    "permission": "⛔ 您没有权限执行此操作",
    "not_found": "❓ 未找到相关信息",
    "invalid_format": "⚠️ 格式错误，请检查输入",
    "insufficient_points": "💢 积分不足，无法完成操作"
}

# 按钮文本
BUTTON_TEXTS = {
    "checkin": "📝 签到",
    "stats": "📊 统计",
    "points": "💰 积分",
    "verify": "📧 验证邮箱",
    "help": "❓ 帮助",
    "confirm": "✅ 确认",
    "cancel": "❌ 取消"
} 