#!/usr/bin/env python3
"""
Coser社群机器人 - 部署前检查脚本
用于检查项目是否准备好进行部署
"""

import os
import sys
import logging
import importlib
import platform
import sqlite3
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("deployment_check")

def check_python_version():
    """检查Python版本"""
    current_version = sys.version_info
    logger.info(f"当前Python版本: {sys.version}")
    
    if current_version.major != 3 or current_version.minor < 8:
        logger.error("需要Python 3.8+版本, 当前版本不满足要求")
        return False
    
    logger.info("✅ Python版本检查通过")
    return True

def check_dependencies():
    """检查依赖项"""
    required_packages = [
        "python-telegram-bot",
        "python-dotenv",
        "aiohttp",
        "aiosqlite",
        "aiofiles",
        "loguru",
        "pydantic"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package.replace("-", "_"))
            logger.info(f"✅ 找到依赖包: {package}")
        except ImportError:
            logger.error(f"❌ 缺少依赖包: {package}")
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"缺少以下依赖包: {', '.join(missing_packages)}")
        logger.error("请运行: pip install -r requirements.txt")
        return False
    
    logger.info("✅ 所有依赖包检查通过")
    return True

def check_env_file():
    """检查环境变量文件"""
    if not os.path.exists(".env"):
        logger.error("❌ .env文件不存在")
        logger.error("请从.env.example复制一份并配置必要的环境变量")
        return False
    
    # 简单检查是否包含必要的配置项
    with open(".env", "r", encoding="utf-8") as f:
        env_content = f.read()
    
    required_vars = ["BOT_TOKEN", "ADMIN_IDS"]
    missing_vars = []
    
    for var in required_vars:
        if var not in env_content or f"{var}=" in env_content:
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ .env文件缺少以下必要配置: {', '.join(missing_vars)}")
        return False
    
    logger.info("✅ .env文件检查通过")
    return True

def check_directory_structure():
    """检查目录结构"""
    required_dirs = ["logs", "data", "backups"]
    missing_dirs = []
    
    for dir_name in required_dirs:
        if not os.path.isdir(dir_name):
            logger.error(f"❌ 缺少必要目录: {dir_name}")
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        logger.error("请创建以下目录:")
        for dir_name in missing_dirs:
            logger.error(f"  mkdir -p {dir_name}")
        return False
    
    logger.info("✅ 目录结构检查通过")
    return True

def check_database():
    """检查数据库文件"""
    db_path = os.environ.get("DATABASE_PATH", "coser_bot.db")
    
    if not os.path.exists(db_path):
        logger.warning(f"⚠️ 数据库文件不存在: {db_path}")
        logger.info("首次运行时将自动创建数据库")
        return True
    
    # 尝试连接数据库
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查users表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.error("❌ 数据库文件损坏或不完整: 缺少users表")
            return False
        
        conn.close()
        logger.info("✅ 数据库文件检查通过")
        return True
    except sqlite3.Error as e:
        logger.error(f"❌ 数据库文件访问错误: {e}")
        return False

def check_permissions():
    """检查文件权限"""
    if platform.system() == "Windows":
        logger.info("Windows系统，跳过权限检查")
        return True
    
    # 检查目录权限
    dirs_to_check = ["logs", "data", "backups"]
    for dir_name in dirs_to_check:
        if not os.path.isdir(dir_name):
            continue
        
        if not os.access(dir_name, os.W_OK):
            logger.error(f"❌ 缺少目录写入权限: {dir_name}")
            return False
    
    logger.info("✅ 文件权限检查通过")
    return True

def main():
    """主函数"""
    logger.info("开始部署前检查...")
    
    # 创建一个检查项目列表
    check_items = [
        ("Python版本", check_python_version),
        ("依赖项", check_dependencies),
        ("环境变量", check_env_file),
        ("目录结构", check_directory_structure),
        ("数据库", check_database),
        ("文件权限", check_permissions)
    ]
    
    # 运行所有检查
    failed_checks = []
    for name, check_func in check_items:
        logger.info(f"\n检查 {name}...")
        if not check_func():
            failed_checks.append(name)
    
    # 输出检查结果
    logger.info("\n" + "="*50)
    logger.info("部署前检查完成")
    logger.info("="*50)
    
    if failed_checks:
        logger.error(f"❌ 有 {len(failed_checks)} 项检查未通过: {', '.join(failed_checks)}")
        logger.error("请解决上述问题后再部署")
        return False
    else:
        logger.info("✅ 所有检查通过！项目已准备好部署")
        return True

if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0 if result else 1)
    except Exception as e:
        logger.exception(f"检查过程中发生错误: {e}")
        sys.exit(1) 