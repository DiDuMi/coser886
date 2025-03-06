"""
@description: 数据存储模块，负责数据的持久化存储和读取
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, date, timedelta
import shutil
from pathlib import Path

from ..config import config
from .models import (
    User, CheckinRecord, PointsTransaction, EmailVerification,
    Group, UserGroupAccess, PointsTransactionType, TransactionStatus, EmailVerifyStatus,
    RecoveryRequest, RecoveryStatus
)

logger = logging.getLogger(__name__)

class Storage:
    """数据存储类，负责数据的持久化存储和读取"""
    
    def __init__(self, data_dir: str = None):
        """
        @description: 初始化存储对象
        @param {str} data_dir: 数据存储目录
        """
        self.data_dir = data_dir or config.DATA_DIR
        self._ensure_dirs_exist()
        
        # 文件路径
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.checkin_records_file = os.path.join(self.data_dir, "checkin_records.json")
        self.transactions_file = os.path.join(self.data_dir, "transactions.json")
        self.email_verifications_file = os.path.join(self.data_dir, "email_verifications.json")
        self.groups_file = os.path.join(self.data_dir, "groups.json")
        self.user_group_access_file = os.path.join(self.data_dir, "user_group_access.json")
        self.recovery_requests_file = os.path.join(self.data_dir, "recovery_requests.json")
        self.invite_links_file = os.path.join(self.data_dir, "invite_links.json")
        
        # 内存缓存
        self.users: Dict[int, User] = {}
        self.checkin_records: List[CheckinRecord] = []
        self.transactions: List[PointsTransaction] = []
        self.email_verifications: List[EmailVerification] = []
        self.groups: Dict[int, Group] = {}
        self.user_group_access: List[UserGroupAccess] = []
        self.recovery_requests: List[RecoveryRequest] = []
        self.invite_links: List[Dict[str, Any]] = []
        
        # 加载数据
        self._load_data()
    
    def _ensure_dirs_exist(self):
        """确保必要的目录存在"""
        # 创建数据目录
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(config.BACKUP_DIR, exist_ok=True)
        
        # 确保所有数据文件存在
        for file_name in [
            "users.json", 
            "checkin_records.json", 
            "transactions.json",
            "email_verifications.json", 
            "groups.json", 
            "user_group_access.json",
            "recovery_requests.json", 
            "invite_links.json"
        ]:
            file_path = os.path.join(self.data_dir, file_name)
            if not os.path.exists(file_path):
                # 创建空的 JSON 文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    if file_name == "users.json":
                        json.dump([], f)  # 空用户列表
                    elif file_name == "groups.json":
                        # 初始化默认群组
                        json.dump([
                            {
                                "group_id": 1,
                                "group_name": "Coser社群",
                                "chat_id": -1002295555543,
                                "is_paid": False,
                                "required_points": 0,
                                "access_days": 0,
                                "is_topics_group": True,
                                "created_at": datetime.now().isoformat()
                            },
                            {
                                "group_id": 2,
                                "group_name": "Coser权益群",
                                "chat_id": -1002317028637,
                                "is_paid": True,
                                "required_points": 1000,
                                "access_days": 30,
                                "is_topics_group": False,
                                "created_at": datetime.now().isoformat()
                            }
                        ], f, ensure_ascii=False, indent=2)
                    else:
                        json.dump([], f)  # 其他文件使用空列表
    
    def _load_data(self):
        """从文件加载数据到内存"""
        # 加载用户数据
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)
                    for user_data in users_data:
                        user = User.from_dict(user_data)
                        self.users[user.user_id] = user
                logger.info(f"已加载 {len(self.users)} 个用户数据")
            except Exception as e:
                logger.error(f"加载用户数据失败: {e}")
        
        # 加载签到记录
        if os.path.exists(self.checkin_records_file):
            try:
                with open(self.checkin_records_file, 'r', encoding='utf-8') as f:
                    records_data = json.load(f)
                    self.checkin_records = [CheckinRecord.from_dict(record) for record in records_data]
                logger.info(f"已加载 {len(self.checkin_records)} 条签到记录")
            except Exception as e:
                logger.error(f"加载签到记录失败: {e}")
        
        # 加载积分交易记录
        if os.path.exists(self.transactions_file):
            try:
                with open(self.transactions_file, 'r', encoding='utf-8') as f:
                    transactions_data = json.load(f)
                    self.transactions = [PointsTransaction.from_dict(tx) for tx in transactions_data]
                logger.info(f"已加载 {len(self.transactions)} 条积分交易记录")
            except Exception as e:
                logger.error(f"加载积分交易记录失败: {e}")
        
        # 加载邮箱验证记录
        if os.path.exists(self.email_verifications_file):
            try:
                with open(self.email_verifications_file, 'r', encoding='utf-8') as f:
                    verifications_data = json.load(f)
                    self.email_verifications = [EmailVerification.from_dict(v) for v in verifications_data]
                logger.info(f"已加载 {len(self.email_verifications)} 条邮箱验证记录")
            except Exception as e:
                logger.error(f"加载邮箱验证记录失败: {e}")
        
        # 加载群组数据
        if os.path.exists(self.groups_file):
            try:
                with open(self.groups_file, 'r', encoding='utf-8') as f:
                    groups_data = json.load(f)
                    for group_data in groups_data:
                        group = Group.from_dict(group_data)
                        self.groups[group.group_id] = group
                logger.info(f"已加载 {len(self.groups)} 个群组数据")
            except Exception as e:
                logger.error(f"加载群组数据失败: {e}")
        
        # 加载用户群组访问权限
        if os.path.exists(self.user_group_access_file):
            try:
                with open(self.user_group_access_file, 'r', encoding='utf-8') as f:
                    access_data = json.load(f)
                    self.user_group_access = [UserGroupAccess.from_dict(a) for a in access_data]
                logger.info(f"已加载 {len(self.user_group_access)} 条用户群组访问权限")
            except Exception as e:
                logger.error(f"加载用户群组访问权限失败: {e}")
        
        # 加载恢复请求数据
        if os.path.exists(self.recovery_requests_file):
            try:
                with open(self.recovery_requests_file, 'r', encoding='utf-8') as f:
                    requests_data = json.load(f)
                    self.recovery_requests = [RecoveryRequest.from_dict(r) for r in requests_data]
                logger.info(f"已加载 {len(self.recovery_requests)} 条恢复请求")
            except Exception as e:
                logger.error(f"加载恢复请求失败: {e}")
        
        # 加载邀请链接数据
        if os.path.exists(self.invite_links_file):
            try:
                with open(self.invite_links_file, 'r', encoding='utf-8') as f:
                    self.invite_links = json.load(f)
                logger.info(f"已加载 {len(self.invite_links)} 条邀请链接")
            except Exception as e:
                logger.error(f"加载邀请链接失败: {e}")
    
    def _save_data(self):
        """将内存数据保存到文件"""
        # 保存用户数据
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                users_data = [user.to_dict() for user in self.users.values()]
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.users)} 个用户数据")
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
        
        # 保存签到记录
        try:
            with open(self.checkin_records_file, 'w', encoding='utf-8') as f:
                records_data = [record.to_dict() for record in self.checkin_records]
                json.dump(records_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.checkin_records)} 条签到记录")
        except Exception as e:
            logger.error(f"保存签到记录失败: {e}")
        
        # 保存积分交易记录
        try:
            with open(self.transactions_file, 'w', encoding='utf-8') as f:
                transactions_data = [tx.to_dict() for tx in self.transactions]
                json.dump(transactions_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.transactions)} 条积分交易记录")
        except Exception as e:
            logger.error(f"保存积分交易记录失败: {e}")
        
        # 保存邮箱验证记录
        try:
            with open(self.email_verifications_file, 'w', encoding='utf-8') as f:
                verifications_data = [v.to_dict() for v in self.email_verifications]
                json.dump(verifications_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.email_verifications)} 条邮箱验证记录")
        except Exception as e:
            logger.error(f"保存邮箱验证记录失败: {e}")
        
        # 保存群组数据
        try:
            with open(self.groups_file, 'w', encoding='utf-8') as f:
                groups_data = [group.to_dict() for group in self.groups.values()]
                json.dump(groups_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.groups)} 个群组数据")
        except Exception as e:
            logger.error(f"保存群组数据失败: {e}")
        
        # 保存用户群组访问权限
        try:
            with open(self.user_group_access_file, 'w', encoding='utf-8') as f:
                access_data = [access.to_dict() for access in self.user_group_access]
                json.dump(access_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.user_group_access)} 条用户群组访问权限")
        except Exception as e:
            logger.error(f"保存用户群组访问权限失败: {e}")
        
        # 保存恢复请求数据
        try:
            with open(self.recovery_requests_file, 'w', encoding='utf-8') as f:
                requests_data = [r.to_dict() for r in self.recovery_requests]
                json.dump(requests_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存恢复请求失败: {e}")
        
        # 保存邀请链接数据
        try:
            with open(self.invite_links_file, 'w', encoding='utf-8') as f:
                json.dump(self.invite_links, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存邀请链接失败: {e}")
    
    def backup_data(self):
        """备份数据"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(config.BACKUP_DIR, f"backup_{timestamp}")
        os.makedirs(backup_dir, exist_ok=True)
        
        try:
            # 先保存当前数据
            self._save_data()
            
            # 复制所有数据文件到备份目录
            for file_name in ["users.json", "checkin_records.json", "transactions.json", 
                             "email_verifications.json", "groups.json", "user_group_access.json",
                             "recovery_requests.json", "invite_links.json"]:
                src_file = os.path.join(self.data_dir, file_name)
                if os.path.exists(src_file):
                    shutil.copy2(src_file, os.path.join(backup_dir, file_name))
            
            logger.info(f"数据已备份到 {backup_dir}")
            return True
        except Exception as e:
            logger.error(f"数据备份失败: {e}")
            return False
    
    # 用户相关方法
    def get_user(self, user_id: int) -> Optional[User]:
        """
        @description: 获取用户信息
        @param {int} user_id: 用户ID
        @return {Optional[User]}: 用户对象，不存在则返回None
        """
        return self.users.get(user_id)
    
    def save_user(self, user: User) -> bool:
        """
        @description: 保存用户信息
        @param {User} user: 用户对象
        @return {bool}: 是否保存成功
        """
        try:
            self.users[user.user_id] = user
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"保存用户信息失败: {e}")
            return False
    
    def get_all_users(self) -> List[User]:
        """
        获取所有用户列表
        
        Returns:
            List[User]: 用户列表
        """
        try:
            users = list(self.users.values())
            logger.debug(f"获取所有用户成功，共 {len(users)} 个用户")
            return users
        except Exception as e:
            logger.error(f"获取所有用户失败: {e}", exc_info=True)
            return []
    
    # 签到记录相关方法
    def add_checkin_record(self, record: CheckinRecord) -> bool:
        """
        @description: 添加签到记录
        @param {CheckinRecord} record: 签到记录对象
        @return {bool}: 是否添加成功
        """
        try:
            # 设置记录ID
            if record.record_id is None:
                record.record_id = len(self.checkin_records) + 1
            
            self.checkin_records.append(record)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"添加签到记录失败: {e}")
            return False
    
    def get_user_checkin_records(self, user_id: int, limit: int = 30) -> List[CheckinRecord]:
        """
        @description: 获取用户的签到记录
        @param {int} user_id: 用户ID
        @param {int} limit: 返回记录数量限制
        @return {List[CheckinRecord]}: 签到记录列表
        """
        records = [r for r in self.checkin_records if r.user_id == user_id]
        records.sort(key=lambda r: r.checkin_date, reverse=True)
        return records[:limit]
    
    def get_user_checkin_record_by_date(self, user_id: int, checkin_date: date) -> Optional[CheckinRecord]:
        """
        @description: 获取用户指定日期的签到记录
        @param {int} user_id: 用户ID
        @param {date} checkin_date: 签到日期
        @return {Optional[CheckinRecord]}: 签到记录，不存在则返回None
        """
        for record in self.checkin_records:
            if record.user_id == user_id and record.checkin_date == checkin_date:
                return record
        return None
    
    def get_user_last_checkin_record(self, user_id: int) -> Optional[CheckinRecord]:
        """
        @description: 获取用户最后一次签到记录
        @param {int} user_id: 用户ID
        @return {Optional[CheckinRecord]}: 签到记录，不存在则返回None
        """
        user_records = [r for r in self.checkin_records if r.user_id == user_id]
        if not user_records:
            return None
        
        return max(user_records, key=lambda r: r.checkin_date)
    
    def get_user_continuous_checkin_days(self, user_id: int) -> int:
        """
        @description: 获取用户连续签到天数
        @param {int} user_id: 用户ID
        @return {int}: 连续签到天数
        """
        user = self.get_user(user_id)
        if not user:
            return 0
        
        return user.streak_days
    
    # 积分交易相关方法
    def add_transaction(self, transaction: PointsTransaction) -> bool:
        """
        @description: 添加积分交易记录
        @param {PointsTransaction} transaction: 积分交易记录对象
        @return {bool}: 是否添加成功
        """
        try:
            # 设置交易ID
            if transaction.transaction_id is None:
                transaction.transaction_id = len(self.transactions) + 1
            
            self.transactions.append(transaction)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"添加积分交易记录失败: {e}")
            return False
    
    def save_transaction(self, transaction: PointsTransaction) -> bool:
        """
        @description: 保存积分交易记录（与add_transaction功能相同，为兼容性保留）
        @param {PointsTransaction} transaction: 积分交易记录对象
        @return {bool}: 是否保存成功
        """
        return self.add_transaction(transaction)
    
    def get_user_transactions(self, user_id: int, limit: int = 30) -> List[PointsTransaction]:
        """
        @description: 获取用户的积分交易记录
        @param {int} user_id: 用户ID
        @param {int} limit: 返回记录数量限制
        @return {List[PointsTransaction]}: 积分交易记录列表
        """
        transactions = [t for t in self.transactions if t.user_id == user_id]
        transactions.sort(key=lambda t: t.created_at, reverse=True)
        return transactions[:limit]
    
    def get_user_gift_transactions(self, user_id: int, limit: int = 10) -> List[PointsTransaction]:
        """获取用户的赠送记录
        
        Args:
            user_id: 用户ID
            limit: 返回记录数量限制
            
        Returns:
            List[PointsTransaction]: 赠送记录列表
        """
        # 过滤出与该用户相关的赠送和接收记录
        gift_transactions = [
            t for t in self.transactions 
            if (t.user_id == user_id or t.related_user_id == user_id) 
            and t.transaction_type in [PointsTransactionType.GIFT_SENT, PointsTransactionType.GIFT_RECEIVED]
        ]
        
        # 按时间倒序排序并限制数量
        return sorted(gift_transactions, key=lambda x: x.created_at, reverse=True)[:limit]
    
    # 邮箱验证相关方法
    def add_email_verification(self, verification: EmailVerification) -> bool:
        """
        @description: 添加邮箱验证记录
        @param {EmailVerification} verification: 邮箱验证记录对象
        @return {bool}: 是否添加成功
        """
        try:
            # 设置验证ID
            if verification.verification_id is None:
                verification.verification_id = len(self.email_verifications) + 1
            
            self.email_verifications.append(verification)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"添加邮箱验证记录失败: {e}")
            return False
    
    def get_email_verifications_by_user(self, user_id: int) -> List[EmailVerification]:
        """
        @description: 获取用户的邮箱验证记录
        @param {int} user_id: 用户ID
        @return {List[EmailVerification]}: 邮箱验证记录列表
        """
        return [v for v in self.email_verifications if v.user_id == user_id]
    
    def get_email_verification(self, user_id: int, verification_code: str) -> Optional[EmailVerification]:
        """
        @description: 获取邮箱验证记录
        @param {int} user_id: 用户ID
        @param {str} verification_code: 验证码
        @return {Optional[EmailVerification]}: 验证记录，不存在则返回None
        """
        for verification in self.email_verifications:
            if verification.user_id == user_id and verification.verification_code == verification_code:
                return verification
        return None
    
    def get_email_verification_by_code(self, verification_code: str) -> Optional[EmailVerification]:
        """
        @description: 通过验证码获取邮箱验证记录
        @param {str} verification_code: 验证码
        @return {Optional[EmailVerification]}: 验证记录，不存在则返回None
        """
        for verification in self.email_verifications:
            if verification.verification_code == verification_code:
                return verification
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        @description: 根据邮箱获取用户
        @param {str} email: 邮箱
        @return {Optional[User]}: 用户对象
        """
        self._load_data()
        for user in self.users.values():
            if user.email == email:
                return user
        return None
    
    def get_user_pending_email_verifications(self, user_id: int) -> List[EmailVerification]:
        """
        @description: 获取用户待处理的邮箱验证记录
        @param {int} user_id: 用户ID
        @return {List[EmailVerification]}: 邮箱验证记录列表
        """
        return [v for v in self.email_verifications 
                if v.user_id == user_id and v.status == EmailVerifyStatus.PENDING]
    
    # 群组相关方法
    def get_group(self, group_id: int) -> Optional[Group]:
        """
        @description: 获取群组信息
        @param {int} group_id: 群组ID
        @return {Optional[Group]}: 群组对象，不存在则返回None
        """
        return self.groups.get(group_id)
    
    def save_group(self, group: Group) -> bool:
        """
        @description: 保存群组信息
        @param {Group} group: 群组对象
        @return {bool}: 是否保存成功
        """
        try:
            self.groups[group.group_id] = group
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"保存群组信息失败: {e}")
            return False
    
    def get_all_groups(self) -> List[Group]:
        """
        @description: 获取所有群组
        @return {List[Group]}: 群组列表
        """
        return list(self.groups.values())
    
    # 用户群组访问权限相关方法
    def add_user_group_access(self, access: UserGroupAccess) -> bool:
        """
        @description: 添加用户群组访问权限
        @param {UserGroupAccess} access: 用户群组访问权限对象
        @return {bool}: 是否添加成功
        """
        try:
            # 设置访问ID
            if access.access_id is None:
                access.access_id = len(self.user_group_access) + 1
            
            self.user_group_access.append(access)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"添加用户群组访问权限失败: {e}")
            return False
    
    def get_user_group_access(self, user_id: int, group_id: int) -> Optional[UserGroupAccess]:
        """
        @description: 获取用户群组访问权限
        @param {int} user_id: 用户ID
        @param {int} group_id: 群组ID
        @return {Optional[UserGroupAccess]}: 用户群组访问权限对象，不存在则返回None
        """
        for access in self.user_group_access:
            if access.user_id == user_id and access.group_id == group_id:
                return access
        return None
    
    def get_user_group_accesses(self, user_id: int) -> List[UserGroupAccess]:
        """
        @description: 获取用户的所有群组访问权限
        @param {int} user_id: 用户ID
        @return {List[UserGroupAccess]}: 用户群组访问权限列表
        """
        return [a for a in self.user_group_access if a.user_id == user_id]
    
    def get_group_user_accesses(self, group_id: int) -> List[UserGroupAccess]:
        """
        @description: 获取群组的所有用户访问权限
        @param {int} group_id: 群组ID
        @return {List[UserGroupAccess]}: 用户群组访问权限列表
        """
        return [a for a in self.user_group_access if a.group_id == group_id]
    
    # 恢复请求相关方法
    def add_recovery_request(self, request: RecoveryRequest) -> bool:
        """
        @description: 添加恢复请求
        @param {RecoveryRequest} request: 恢复请求对象
        @return {bool}: 是否添加成功
        """
        try:
            # 检查是否已存在相同ID的请求
            for i, r in enumerate(self.recovery_requests):
                if r.request_id == request.request_id:
                    # 更新现有请求
                    self.recovery_requests[i] = request
                    self._save_data()
                    return True
            
            # 添加新请求
            self.recovery_requests.append(request)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"添加恢复请求失败: {e}")
            return False
    
    def get_recovery_request(self, request_id: str) -> Optional[RecoveryRequest]:
        """
        @description: 获取恢复请求
        @param {str} request_id: 请求ID
        @return {Optional[RecoveryRequest]}: 恢复请求对象，不存在则返回None
        """
        for request in self.recovery_requests:
            if request.request_id == request_id:
                return request
        return None
    
    def get_pending_recovery_request_by_new_user(self, user_id: int) -> Optional[RecoveryRequest]:
        """
        @description: 获取用户的待处理恢复请求
        @param {int} user_id: 新用户ID
        @return {Optional[RecoveryRequest]}: 恢复请求对象，不存在则返回None
        """
        for request in self.recovery_requests:
            if request.new_user_id == user_id and request.status == RecoveryStatus.PENDING:
                return request
        return None
    
    def get_recovery_requests_by_old_user(self, user_id: int) -> List[RecoveryRequest]:
        """
        @description: 获取原用户的所有恢复请求
        @param {int} user_id: 原用户ID
        @return {List[RecoveryRequest]}: 恢复请求列表
        """
        return [r for r in self.recovery_requests if r.old_user_id == user_id]
    
    def get_recovery_requests_by_new_user(self, user_id: int) -> List[RecoveryRequest]:
        """
        @description: 获取新用户的所有恢复请求
        @param {int} user_id: 新用户ID
        @return {List[RecoveryRequest]}: 恢复请求列表
        """
        return [r for r in self.recovery_requests if r.new_user_id == user_id]
    
    def get_recovery_requests_by_email(self, email: str) -> List[RecoveryRequest]:
        """
        @description: 获取邮箱的所有恢复请求
        @param {str} email: 邮箱地址
        @return {List[RecoveryRequest]}: 恢复请求列表
        """
        return [r for r in self.recovery_requests if r.email == email]
    
    def add_invite_link(self, group_id: int, user_id: int, invite_link: str, expires_at: datetime) -> bool:
        """
        @description: 添加邀请链接
        @param {int} group_id: 群组ID
        @param {int} user_id: 用户ID
        @param {str} invite_link: 邀请链接
        @param {datetime} expires_at: 过期时间
        @return {bool}: 是否添加成功
        """
        try:
            invite_data = {
                "group_id": group_id,
                "user_id": user_id,
                "invite_link": invite_link,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat(),
                "is_used": False
            }
            
            self.invite_links.append(invite_data)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"添加邀请链接失败: {e}")
            return False
    
    def get_user_invite_links(self, user_id: int) -> List[Dict[str, Any]]:
        """
        @description: 获取用户的所有邀请链接
        @param {int} user_id: 用户ID
        @return {List[Dict[str, Any]]}: 邀请链接列表
        """
        return [link for link in self.invite_links if link["user_id"] == user_id]
    
    def mark_invite_link_used(self, invite_link: str) -> bool:
        """
        @description: 标记邀请链接为已使用
        @param {str} invite_link: 邀请链接
        @return {bool}: 是否标记成功
        """
        try:
            for link in self.invite_links:
                if link["invite_link"] == invite_link:
                    link["is_used"] = True
                    self._save_data()
                    return True
            return False
        except Exception as e:
            logger.error(f"标记邀请链接失败: {e}")
            return False
    
    def update_email_verification(self, verification: EmailVerification) -> bool:
        """
        @description: 更新邮箱验证记录
        @param {EmailVerification} verification: 验证记录
        @return {bool}: 是否更新成功
        """
        try:
            for i, v in enumerate(self.email_verifications):
                if v.user_id == verification.user_id and v.verification_code == verification.verification_code:
                    self.email_verifications[i] = verification
                    self._save_data()
                    return True
            
            # 如果没有找到匹配的记录，添加新记录
            self.email_verifications.append(verification)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"更新邮箱验证记录失败: {e}")
            return False
    
    def update_recovery_request(self, request: RecoveryRequest) -> bool:
        """
        更新恢复请求
        @param request: 恢复请求对象
        @return: 是否更新成功
        """
        try:
            # 检查是否存在该请求
            for i, r in enumerate(self.recovery_requests):
                if r.request_id == request.request_id:
                    # 更新请求
                    self.recovery_requests[i] = request
                    self._save_data()
                    return True
            
            # 如果不存在，添加新请求
            self.recovery_requests.append(request)
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"更新恢复请求失败: {str(e)}")
            return False

    def get_user_groups(self, user_id: int) -> List[Group]:
        """
        获取用户所在的权益群组
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Group]: 用户所在的群组列表
        """
        try:
            logger.info(f"获取用户 {user_id} 的群组信息")
            
            # 获取用户的群组访问记录
            accesses = [
                access for access in self.user_group_access 
                if access.user_id == user_id 
                and (not access.end_date or access.end_date > datetime.now())
            ]
            
            logger.info(f"找到 {len(accesses)} 条有效的群组访问记录")
            
            # 获取对应的群组信息
            groups = []
            for access in accesses:
                group = self.groups.get(access.group_id)
                if group:
                    groups.append(group)
                    logger.info(f"用户在群组: {group.group_name} (ID: {group.group_id})")
                else:
                    logger.warning(f"未找到群组ID {access.group_id} 的信息")
                
            logger.info(f"用户共在 {len(groups)} 个群组中")
            return groups
        
        except Exception as e:
            logger.error(f"获取用户 {user_id} 的群组信息时出错: {e}")
            return []

    def get_group_by_chat_id(self, chat_id: int) -> Optional[Group]:
        """
        通过 chat_id 获取群组信息
        
        Args:
            chat_id: Telegram 群组的 chat_id
            
        Returns:
            Optional[Group]: 群组对象，不存在则返回 None
        """
        for group in self.groups.values():
            if group.chat_id == chat_id:
                return group
        return None

    def get_user_total_earned(self, user_id: int) -> int:
        """
        @description: 获取用户总收入积分
        @param {int} user_id: 用户ID
        @return {int}: 总收入积分
        """
        self._load_data()
        total = 0
        for tx in self.transactions:
            if tx.user_id == user_id and tx.amount > 0:
                total += tx.amount
        return total
        
    def get_user_total_spent(self, user_id: int) -> int:
        """
        @description: 获取用户总支出积分
        @param {int} user_id: 用户ID
        @return {int}: 总支出积分（正数）
        """
        self._load_data()
        total = 0
        for tx in self.transactions:
            if tx.user_id == user_id and tx.amount < 0:
                total += abs(tx.amount)
        return total

# 创建全局存储实例
storage = Storage()
storage._load_data() 