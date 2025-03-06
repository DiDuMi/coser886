import json
import os
import sqlite3
from datetime import datetime

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect('data/coser_bot.db')
    c = conn.cursor()
    
    # 创建用户表
    c.execute('''
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
    ''')
    
    # 创建积分交易表
    c.execute('''
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
    ''')
    
    # 创建邮箱验证表
    c.execute('''
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
    ''')
    
    # 创建签到记录表
    c.execute('''
    CREATE TABLE IF NOT EXISTS checkin_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        checkin_date DATE,
        points_earned INTEGER,
        streak_bonus INTEGER DEFAULT 0,
        created_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    return conn

def import_data():
    """从JSON文件导入数据"""
    conn = init_db()
    c = conn.cursor()
    
    # 导入用户数据
    with open('data/users.json', 'r', encoding='utf-8') as f:
        users = json.load(f)
        for user in users:
            c.execute('''
            INSERT INTO users (
                user_id, username, join_date, points, frozen_points,
                email, email_verified, last_email_change,
                last_checkin_date, streak_days, total_checkins,
                monthly_checkins, makeup_chances
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user['user_id'], user['username'], user.get('join_date'),
                user.get('points', 0), user.get('frozen_points', 0),
                user.get('email'), user.get('email_verified', False),
                user.get('last_email_change'), user.get('last_checkin_date'),
                user.get('streak_days', 0), user.get('total_checkins', 0),
                user.get('monthly_checkins', 0), user.get('makeup_chances', 1)
            ))
    
    # 导入交易记录
    with open('data/transactions.json', 'r', encoding='utf-8') as f:
        transactions = json.load(f)
        for tx in transactions:
            c.execute('''
            INSERT INTO points_transactions (
                user_id, amount, transaction_type, description,
                created_at, related_user_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                tx['user_id'], tx['amount'], tx['transaction_type'],
                tx['description'], tx['created_at'], tx.get('related_user_id')
            ))
    
    # 导入邮箱验证记录
    with open('data/email_verifications.json', 'r', encoding='utf-8') as f:
        verifications = json.load(f)
        for v in verifications:
            c.execute('''
            INSERT INTO email_verifications (
                user_id, email, code, created_at, expires_at, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                v['user_id'], v['email'], v['code'],
                v['created_at'], v['expires_at'], v['status']
            ))
    
    # 导入签到记录
    with open('data/checkin_records.json', 'r', encoding='utf-8') as f:
        records = json.load(f)
        for r in records:
            c.execute('''
            INSERT INTO checkin_records (
                user_id, checkin_date, points_earned,
                streak_bonus, created_at
            ) VALUES (?, ?, ?, ?, ?)
            ''', (
                r['user_id'], r['checkin_date'], r['points_earned'],
                r.get('streak_bonus', 0), r['created_at']
            ))
    
    conn.commit()
    conn.close()
    print("数据导入完成！")

if __name__ == '__main__':
    import_data() 