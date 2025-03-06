"""
@description: 数据模型模块，定义系统中使用的数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union
from enum import Enum, auto
from ..config.constants import (
    PointsTransactionType,
    EmailVerifyStatus,
    MessageType,
    UserRole
)

class TransactionStatus(Enum):
    """交易状态枚举"""
    PENDING = "待处理"
    COMPLETED = "已完成"
    REJECTED = "已拒绝"
    EXPIRED = "已过期"
    CANCELLED = "已取消"

class RecoveryStatus(Enum):
    """恢复请求状态枚举"""
    PENDING = "待处理"
    APPROVED = "已批准"
    REJECTED = "已拒绝"
    EXPIRED = "已过期"
    CANCELLED = "已取消"

@dataclass
class User:
    """用户数据模型"""
    user_id: int
    username: str
    first_name: str = None
    join_date: datetime = field(default_factory=datetime.now)
    points: int = 0
    frozen_points: int = 0
    email: Optional[str] = None
    email_verified: bool = False
    last_email_change: Optional[datetime] = None
    last_checkin_date: Optional[date] = None
    streak_days: int = 0
    max_streak_days: int = 0
    total_checkins: int = 0
    monthly_checkins: int = 0
    makeup_chances: int = 1
    is_migrated: bool = False
    migrated_to: Optional[int] = None
    total_points_earned: int = 0  # 累计获得的总积分
    total_points_spent: int = 0   # 累计消费的总积分
    longest_streak_start: Optional[date] = None  # 最长连续签到开始日期
    longest_streak_end: Optional[date] = None    # 最长连续签到结束日期
    last_week_checkins: int = 0   # 最近一周签到次数
    last_month_checkins: int = 0  # 最近一个月签到次数
    checkin_streak: int = 0       # 当前连续签到天数
    login_days: int = 0           # 累计登录天数
    invited_users: int = 0        # 邀请的用户数量
    last_checkin: Optional[datetime] = None  # 最后签到时间
    last_active: Optional[datetime] = None   # 最后活动时间
    
    def to_dict(self) -> Dict[str, Any]:
        """
        @description: 将用户对象转换为字典
        @return {Dict[str, Any]}: 用户信息字典
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "join_date": self.join_date.isoformat() if self.join_date else None,
            "points": self.points,
            "frozen_points": self.frozen_points,
            "email": self.email,
            "email_verified": self.email_verified,
            "last_email_change": self.last_email_change.isoformat() if self.last_email_change else None,
            "last_checkin_date": self.last_checkin_date.isoformat() if self.last_checkin_date else None,
            "streak_days": self.streak_days,
            "max_streak_days": self.max_streak_days,
            "total_checkins": self.total_checkins,
            "monthly_checkins": self.monthly_checkins,
            "makeup_chances": self.makeup_chances,
            "is_migrated": self.is_migrated,
            "migrated_to": self.migrated_to,
            "total_points_earned": self.total_points_earned,
            "total_points_spent": self.total_points_spent,
            "longest_streak_start": self.longest_streak_start.isoformat() if self.longest_streak_start else None,
            "longest_streak_end": self.longest_streak_end.isoformat() if self.longest_streak_end else None,
            "last_week_checkins": self.last_week_checkins,
            "last_month_checkins": self.last_month_checkins,
            "checkin_streak": self.checkin_streak,
            "login_days": self.login_days,
            "invited_users": self.invited_users,
            "last_checkin": self.last_checkin.isoformat() if self.last_checkin else None,
            "last_active": self.last_active.isoformat() if self.last_active else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        @description: 从字典创建用户对象
        @param {Dict[str, Any]} data: 用户信息字典
        @return {User}: 用户对象
        """
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            first_name=data.get("first_name"),
            join_date=datetime.fromisoformat(data["join_date"]) if data.get("join_date") else datetime.now(),
            points=data.get("points", 0),
            frozen_points=data.get("frozen_points", 0),
            email=data.get("email"),
            email_verified=data.get("email_verified", False),
            last_email_change=datetime.fromisoformat(data["last_email_change"]) if data.get("last_email_change") else None,
            last_checkin_date=date.fromisoformat(data["last_checkin_date"]) if data.get("last_checkin_date") else None,
            streak_days=data.get("streak_days", 0),
            max_streak_days=data.get("max_streak_days", 0),
            total_checkins=data.get("total_checkins", 0),
            monthly_checkins=data.get("monthly_checkins", 0),
            makeup_chances=data.get("makeup_chances", 1),
            is_migrated=data.get("is_migrated", False),
            migrated_to=data.get("migrated_to"),
            total_points_earned=data.get("total_points_earned", 0),
            total_points_spent=data.get("total_points_spent", 0),
            longest_streak_start=date.fromisoformat(data["longest_streak_start"]) if data.get("longest_streak_start") else None,
            longest_streak_end=date.fromisoformat(data["longest_streak_end"]) if data.get("longest_streak_end") else None,
            last_week_checkins=data.get("last_week_checkins", 0),
            last_month_checkins=data.get("last_month_checkins", 0),
            checkin_streak=data.get("checkin_streak", 0),
            login_days=data.get("login_days", 0),
            invited_users=data.get("invited_users", 0),
            last_checkin=datetime.fromisoformat(data["last_checkin"]) if data.get("last_checkin") else None,
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else None
        )

@dataclass
class PointsTransaction:
    """积分交易数据模型"""
    user_id: int
    amount: int
    transaction_type: PointsTransactionType
    description: str
    created_at: datetime = field(default_factory=datetime.now)
    related_user_id: Optional[int] = None
    transaction_id: Optional[int] = None
    status: TransactionStatus = TransactionStatus.COMPLETED
    expires_at: Optional[datetime] = None
    
    @property
    def timestamp(self) -> datetime:
        """
        @description: 获取交易时间戳（兼容性属性，返回created_at）
        @return {datetime}: 交易创建时间
        """
        return self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """
        @description: 将积分交易对象转换为字典
        @return {Dict[str, Any]}: 积分交易信息字典
        """
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "transaction_type": self.transaction_type.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "related_user_id": self.related_user_id,
            "status": self.status.value,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PointsTransaction':
        """
        @description: 从字典创建积分交易对象
        @param {Dict[str, Any]} data: 积分交易信息字典
        @return {PointsTransaction}: 积分交易对象
        """
        return cls(
            transaction_id=data.get("transaction_id"),
            user_id=data["user_id"],
            amount=data["amount"],
            transaction_type=next(t for t in PointsTransactionType if t.value == data["transaction_type"]),
            description=data["description"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            related_user_id=data.get("related_user_id"),
            status=next(s for s in TransactionStatus if s.value == data["status"]) if data.get("status") else TransactionStatus.COMPLETED,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        )

@dataclass
class CheckinRecord:
    """签到记录数据模型"""
    user_id: int
    checkin_date: date
    points_earned: int
    streak_bonus: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    record_id: Optional[int] = None
    is_makeup: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        @description: 将签到记录对象转换为字典
        @return {Dict[str, Any]}: 签到记录信息字典
        """
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "checkin_date": self.checkin_date.isoformat(),
            "points_earned": self.points_earned,
            "streak_bonus": self.streak_bonus,
            "created_at": self.created_at.isoformat(),
            "is_makeup": self.is_makeup
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckinRecord':
        """
        @description: 从字典创建签到记录对象
        @param {Dict[str, Any]} data: 签到记录信息字典
        @return {CheckinRecord}: 签到记录对象
        """
        return cls(
            record_id=data.get("record_id"),
            user_id=data["user_id"],
            checkin_date=date.fromisoformat(data["checkin_date"]),
            points_earned=data["points_earned"],
            streak_bonus=data.get("streak_bonus", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            is_makeup=data.get("is_makeup", False)
        )

@dataclass
class EmailVerification:
    """邮箱验证数据模型"""
    user_id: int
    email: str
    verification_code: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = None
    status: EmailVerifyStatus = EmailVerifyStatus.PENDING
    verification_id: Optional[int] = None
    
    def __post_init__(self):
        """初始化后处理"""
        from ..config.settings import EMAIL_VERIFICATION_EXPIRY_MINUTES
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(minutes=EMAIL_VERIFICATION_EXPIRY_MINUTES)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        @description: 将邮箱验证对象转换为字典
        @return {Dict[str, Any]}: 邮箱验证信息字典
        """
        status_value = self.status.value if hasattr(self.status, 'value') else self.status
        return {
            "verification_id": self.verification_id,
            "user_id": self.user_id,
            "email": self.email,
            "verification_code": self.verification_code,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "status": status_value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailVerification':
        """
        @description: 从字典创建邮箱验证对象
        @param {Dict[str, Any]} data: 邮箱验证信息字典
        @return {EmailVerification}: 邮箱验证对象
        """
        obj = cls(
            verification_id=data.get("verification_id"),
            user_id=data["user_id"],
            email=data["email"],
            verification_code=data["verification_code"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            status=next(s for s in EmailVerifyStatus if s.value == data["status"]) if data.get("status") else EmailVerifyStatus.PENDING
        )
        return obj

@dataclass
class RecoveryRequest:
    """账号恢复请求数据模型"""
    request_id: str
    old_user_id: int
    new_user_id: int
    email: str
    reason: str
    status: RecoveryStatus = RecoveryStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    process_time: Optional[datetime] = None
    admin_id: Optional[int] = None
    admin_note: Optional[str] = None
    approval_type: Optional[str] = None  # 'full', 'partial', 'points_only'
    
    def to_dict(self) -> Dict[str, Any]:
        """
        @description: 将恢复请求对象转换为字典
        @return {Dict[str, Any]}: 恢复请求信息字典
        """
        status_value = self.status.value if hasattr(self.status, 'value') else self.status
        return {
            "request_id": self.request_id,
            "old_user_id": self.old_user_id,
            "new_user_id": self.new_user_id,
            "email": self.email,
            "reason": self.reason,
            "status": status_value,
            "created_at": self.created_at.isoformat(),
            "process_time": self.process_time.isoformat() if self.process_time else None,
            "admin_id": self.admin_id,
            "admin_note": self.admin_note,
            "approval_type": self.approval_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecoveryRequest':
        """
        @description: 从字典创建恢复请求对象
        @param {Dict[str, Any]} data: 恢复请求信息字典
        @return {RecoveryRequest}: 恢复请求对象
        """
        return cls(
            request_id=data["request_id"],
            old_user_id=data["old_user_id"],
            new_user_id=data["new_user_id"],
            email=data["email"],
            reason=data["reason"],
            status=next(s for s in RecoveryStatus if s.value == data["status"]) if data.get("status") else RecoveryStatus.PENDING,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            process_time=datetime.fromisoformat(data["process_time"]) if data.get("process_time") else None,
            admin_id=data.get("admin_id"),
            admin_note=data.get("admin_note"),
            approval_type=data.get("approval_type")
        )

@dataclass
class Group:
    """群组数据模型"""
    group_id: int
    group_name: str
    chat_id: int
    is_paid: bool = False
    required_points: int = 0
    access_days: int = 0  # 0表示永久
    is_topics_group: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        @description: 将群组对象转换为字典
        @return {Dict[str, Any]}: 群组信息字典
        """
        return {
            "group_id": self.group_id,
            "group_name": self.group_name,
            "chat_id": self.chat_id,
            "is_paid": self.is_paid,
            "required_points": self.required_points,
            "access_days": self.access_days,
            "is_topics_group": self.is_topics_group,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Group':
        """
        @description: 从字典创建群组对象
        @param {Dict[str, Any]} data: 群组信息字典
        @return {Group}: 群组对象
        """
        return cls(
            group_id=data["group_id"],
            group_name=data["group_name"],
            chat_id=data["chat_id"],
            is_paid=data.get("is_paid", False),
            required_points=data.get("required_points", 0),
            access_days=data.get("access_days", 0),
            is_topics_group=data.get("is_topics_group", False),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        )

@dataclass
class UserGroupAccess:
    """用户群组访问权限数据模型"""
    user_id: int
    group_id: int
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None  # None表示永久
    access_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        @description: 将用户群组访问权限对象转换为字典
        @return {Dict[str, Any]}: 用户群组访问权限信息字典
        """
        return {
            "access_id": self.access_id,
            "user_id": self.user_id,
            "group_id": self.group_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserGroupAccess':
        """
        @description: 从字典创建用户群组访问权限对象
        @param {Dict[str, Any]} data: 用户群组访问权限信息字典
        @return {UserGroupAccess}: 用户群组访问权限对象
        """
        return cls(
            access_id=data.get("access_id"),
            user_id=data["user_id"],
            group_id=data["group_id"],
            start_date=datetime.fromisoformat(data["start_date"]) if data.get("start_date") else datetime.now(),
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None
        ) 