# Coser社群机器人

Coser社群Telegram Bot - 用于管理社群互动、签到和积分系统的Telegram机器人。

## 功能特性

- 用户签到系统，支持连续签到奖励
- 积分管理和交易记录
- 社群排行榜
- 邮箱绑定和验证
- 个人信息中心
- 管理员功能和权限控制
- 日志记录和数据备份
- 健康状态监控

## 系统要求

- Python 3.8+
- SQLite 3
- 网络连接以访问Telegram API

## 快速开始

### 本地开发环境

1. 克隆仓库
```bash
git clone https://github.com/your-username/coser-bot.git
cd coser-bot
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 复制环境变量示例文件并进行配置
```bash
cp .env.example .env
# 编辑.env文件，填写您的配置
```

4. 启动机器人
```bash
python simple_bot.py
```

### 宝塔面板部署

1. 通过宝塔面板上传项目代码到服务器
   - 可以使用宝塔的文件管理功能上传ZIP压缩包，也可以通过git克隆

2. 在宝塔面板中安装Python项目管理器和Supervisor管理器插件
   - 在宝塔面板的软件商店中安装"Python项目管理器"插件
   - 在宝塔面板的软件商店中安装"Supervisor管理器"插件

3. 创建Python虚拟环境（可选）
   - 在Python项目管理器中创建新的虚拟环境
   - 选择Python 3.8+版本

4. 配置项目
   - 进入项目目录
   - 创建并配置.env文件: `cp .env.example .env`
   - 编辑.env文件，填写正确的配置信息，特别是BOT_TOKEN和管理员ID

5. 安装依赖
   - 在SSH终端中执行:
   ```bash
   cd /path/to/coser-bot
   python -m pip install -r requirements.txt
   ```

6. 通过Supervisor配置进程管理
   - 在Supervisor管理器插件中添加新程序
   - 名称: coser-bot
   - 启动命令: python /path/to/coser-bot/simple_bot.py
   - 工作目录: /path/to/coser-bot
   - 用户: www
   - 自启动: 是
   - 进程守护: 是

7. 使用部署脚本（可选）
   - 给部署脚本添加执行权限: `chmod +x deploy.sh`
   - 运行部署脚本: `./deploy.sh`

## 目录结构

```
coser-bot/
│
├── simple_bot.py            # 主启动脚本
├── requirements.txt         # 依赖包列表
├── .env.example             # 环境变量示例
├── .env                     # 环境变量配置(需手动创建)
├── README.md                # 项目说明文档
├── deploy.sh                # 部署脚本
│
├── coser_bot/               # 主模块目录
│   ├── __init__.py          # 初始化文件
│   ├── main.py              # 主程序入口
│   ├── config/              # 配置模块
│   ├── database/            # 数据库模块
│   ├── handlers/            # 处理器模块
│   └── utils/               # 工具函数模块
│
├── data/                    # 数据存储目录
├── logs/                    # 日志目录
└── backups/                 # 备份目录
```

## 管理员命令

- `/admin_group_add` - 添加权限组
- `/admin_group_remove` - 移除权限组
- `/admin_group_list` - 列出所有权限组
- `/admin_points` - 调整用户积分
- `/admin_list` - 列出所有用户
- `/admin_info` - 显示用户详细信息
- `/admin_stats` - 显示系统统计信息
- `/health` 或 `/status` - 检查系统健康状态

## 日志和监控

- 日志文件位于 `logs/` 目录下
- 使用 `tail -f logs/supervisor_stdout.log` 查看实时日志
- 健康状态监控可通过 `/health` 命令查看

## 数据备份

系统会自动定期备份数据库到 `backups/` 目录。您也可以手动触发备份:

```bash
cp coser_bot.db backups/coser_bot_$(date +%Y%m%d_%H%M%S).db
```

## 故障排除

1. 启动失败
   - 检查.env配置是否正确
   - 检查日志文件获取详细错误信息
   - 确保端口未被占用(如果使用webhook)

2. 连接超时
   - 检查网络连接
   - 可能是Telegram API访问受限，考虑使用代理

3. 数据库错误
   - 确保有正确的读写权限
   - 尝试从备份恢复数据库

## 联系

如有问题或建议，请联系项目维护人员或提交issue。