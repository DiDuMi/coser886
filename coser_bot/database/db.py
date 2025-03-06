"""
@description: 数据库操作模块，提供数据库的初始化和CRUD操作
"""
import aiosqlite
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from ..config.settings import DATABASE_PATH
from ..config.constants import PointsTransactionType, EmailVerifyStatus
from .models import User, PointsTransaction, EmailVerification, CheckinRecord

logger = logging.getLogger(__name__)

class Database:
    """数据库操作类"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        """
        @description: 初始化数据库连接
        @param {str} db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.connection = None
    
    async def connect(self) -> None:
        """
        @description: 连接数据库
        @return {None}
        """
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            self.connection.row_factory = aiosqlite.Row
            logger.info(f"数据库连接成功: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    async def disconnect(self) -> None:
        """
        @description: 断开数据库连接
        @return {None}
        """
        if self.connection:
            await self.connection.close()
            logger.info("数据库连接已关闭")
    
    async def initialize(self) -> None:
        """
        @description: 初始化数据库表
        @return {None}
        """
        if not self.connection:
            await self.connect()
        
        # 创建用户表
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TIMESTAMP,
            points INTEGER DEFAULT 0,
            frozen_points INTEGER DEFAULT 0,
            email TEXT,
            email_verified BOOLEAN DEFAULT 0,
            last_email_change TIMESTAMP,
            last_checkin_date DATE,
            streak_days INTEGER DEFAULT 0,
            total_checkins INTEGER DEFAULT 0,
            monthly_checkins INTEGER DEFAULT 0,
            makeup_chances INTEGER DEFAULT 1
        )
        """)
        
        # 创建积分交易表
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS points_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            transaction_type TEXT,
            description TEXT,
            created_at TIMESTAMP,
            related_user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """)
        
        # 创建邮箱验证表
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS email_verifications (
            verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT,
            code TEXT,
            created_at TIMESTAMP,
            expires_at TIMESTAMP,
            status TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """)
        
        # 创建签到记录表
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS checkin_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            checkin_date DATE,
            points_earned INTEGER,
            streak_bonus INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """)
        
        await self.connection.commit()
        logger.info("数据库表初始化完成")
    
    # 用户相关操作
    async def get_user(self, user_id: int) -> Optional[User]:
        """
        @description: 获取用户信息
        @param {int} user_id: 用户ID
        @return {Optional[User]}: 用户对象，不存在则返回None
        """
        async with self.connection.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return User(
                    user_id=row['user_id'],
                    username=row['username'],
                    join_date=datetime.fromisoformat(row['join_date']) if row['join_date'] else datetime.now(),
                    points=row['points'],
                    frozen_points=row['frozen_points'],
                    email=row['email'],
                    email_verified=bool(row['email_verified']),
                    last_email_change=datetime.fromisoformat(row['last_email_change']) if row['last_email_change'] else None,
                    last_checkin_date=date.fromisoformat(row['last_checkin_date']) if row['last_checkin_date'] else None,
                    streak_days=row['streak_days'],
                    total_checkins=row['total_checkins'],
                    monthly_checkins=row['monthly_checkins'],
                    makeup_chances=row['makeup_chances']
                )
            return None
    
    async def create_user(self, user: User) -> None:
        """
        @description: 创建新用户
        @param {User} user: 用户对象
        @return {None}
        """
        await self.connection.execute(
            """
            INSERT INTO users (
                user_id, username, join_date, points, frozen_points,
                email, email_verified, last_email_change,
                last_checkin_date, streak_days, total_checkins,
                monthly_checkins, makeup_chances
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.user_id, user.username, user.join_date.isoformat(),
                user.points, user.frozen_points, user.email,
                user.email_verified, user.last_email_change.isoformat() if user.last_email_change else None,
                user.last_checkin_date.isoformat() if user.last_checkin_date else None,
                user.streak_days, user.total_checkins, user.monthly_checkins,
                user.makeup_chances
            )
        )
        await self.connection.commit()
        logger.info(f"创建新用户: {user.user_id} - {user.username}")
    
    async def update_user(self, user: User) -> None:
        """
        @description: 更新用户信息
        @param {User} user: 用户对象
        @return {None}
        """
        await self.connection.execute(
            """
            UPDATE users SET
                username = ?,
                points = ?,
                frozen_points = ?,
                email = ?,
                email_verified = ?,
                last_email_change = ?,
                last_checkin_date = ?,
                streak_days = ?,
                total_checkins = ?,
                monthly_checkins = ?,
                makeup_chances = ?
            WHERE user_id = ?
            """,
            (
                user.username, user.points, user.frozen_points,
                user.email, user.email_verified,
                user.last_email_change.isoformat() if user.last_email_change else None,
                user.last_checkin_date.isoformat() if user.last_checkin_date else None,
                user.streak_days, user.total_checkins, user.monthly_checkins,
                user.makeup_chances, user.user_id
            )
        )
        await self.connection.commit()
        logger.debug(f"更新用户信息: {user.user_id} - {user.username}")
    
    # 积分交易相关操作
    async def add_points_transaction(self, transaction: PointsTransaction) -> int:
        """
        @description: 添加积分交易记录
        @param {PointsTransaction} transaction: 交易对象
        @return {int}: 交易ID
        """
        cursor = await self.connection.execute(
            """
            INSERT INTO points_transactions (
                user_id, amount, transaction_type, description,
                created_at, related_user_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                transaction.user_id, transaction.amount,
                transaction.transaction_type.value, transaction.description,
                transaction.created_at.isoformat(),
                transaction.related_user_id
            )
        )
        await self.connection.commit()
        transaction_id = cursor.lastrowid
        logger.info(f"添加积分交易: ID={transaction_id}, 用户={transaction.user_id}, 金额={transaction.amount}")
        return transaction_id
    
    # 签到记录相关操作
    async def add_checkin_record(self, record: CheckinRecord) -> int:
        """
        @description: 添加签到记录
        @param {CheckinRecord} record: 签到记录对象
        @return {int}: 记录ID
        """
        cursor = await self.connection.execute(
            """
            INSERT INTO checkin_records (
                user_id, checkin_date, points_earned, streak_bonus, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.user_id, record.checkin_date.isoformat(),
                record.points_earned, record.streak_bonus,
                record.created_at.isoformat()
            )
        )
        await self.connection.commit()
        record_id = cursor.lastrowid
        logger.info(f"添加签到记录: ID={record_id}, 用户={record.user_id}, 日期={record.checkin_date}")
        return record_id
    
    # 邮箱验证相关操作
    async def add_email_verification(self, verification: EmailVerification) -> int:
        """
        @description: 添加邮箱验证记录
        @param {EmailVerification} verification: 验证对象
        @return {int}: 验证ID
        """
        cursor = await self.connection.execute(
            """
            INSERT INTO email_verifications (
                user_id, email, code, created_at, expires_at, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                verification.user_id, verification.email, verification.code,
                verification.created_at.isoformat(),
                verification.expires_at.isoformat() if verification.expires_at else None,
                verification.status.value
            )
        )
        await self.connection.commit()
        verification_id = cursor.lastrowid
        logger.info(f"添加邮箱验证: ID={verification_id}, 用户={verification.user_id}, 邮箱={verification.email}")
        return verification_id 