# 步道乐跑任务管理系统

Web 管理后台，用于管理安徽邮电职业技术学院学生的跑步打卡任务。

## 快速开始

```bash
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:5700
# 默认管理员: admin / admin888
```

前端支持独立部署到任意 Web 服务器（nginx / OpenWRT 路由器），详见 [DEPLOY.md](DEPLOY.md)。

## 功能概览

| 模块 | 说明 |
|------|------|
| 📊 概览 | 任务总览、统计图表、学校分布 |
| 📋 任务管理 | 添加/删除/启用禁用任务、修改时间、拉取数据、修改密码 |
| 📁 运行日志 | 按学号分类的运行日志查看 |
| 📜 历史记录 | 从云运动服务器导入历史跑步记录 |
| 📝 操作日志 | 管理员查看全量审计日志 |
| 📬 消息 | 用户查看删除申请结果和账户变动通知 |
| 📞 联系方式 | 用户多联系方式编辑（QQ/微信/邮箱/电话，每类最多5个） |
| 📡 后端管理 | 管理员管理多后端聚合 |

## 用户角色

| 角色 | 权限 |
|------|------|
| 👤 普通用户 | 仅查看自己的任务、运行日志、申请删除、查看消息 |
| 👑 管理员 | 全部任务、管理多后端、审核删除申请、查看操作日志 |

## 登录机制

1. **优先本地数据库** — 管理员首次后端登录后自动同步所有用户到浏览器 localStorage
2. **级联后端** — 主后端不可达时自动尝试其他已配置的后端
3. **完全离线** — 后台全部离线时仍可使用本地账号登录（密码首次联网认证后缓存）

## 文件结构

```
project/
├── server.py              # Flask 后端主程序（所有 REST API）
├── build.py               # 构建单文件版前端（内联 CSS/JS）
├── start.bat              # Windows 一键安装依赖并启动
├── requirements.txt       # Python 依赖清单
├── DEPLOY.md              # 多服务器部署文档
├── README.md              # 本文件
│
├── data/                  # JSON 数据存储
│   ├── tasks.json         # 所有用户任务配置
│   ├── users.json         # 用户账户（用户名、密码、角色、联系方式）
│   ├── devices.json       # 设备池
│   ├── delete_requests.json # 删除申请记录
│   ├── audit_log.json     # 操作审计日志（保留最近 500 条）
│   └── tokens.json        # 登录 Token 持久化
│
├── static/                # 前端源文件
│   ├── index.html         # 主页面（SPA 壳 + 弹窗模板）
│   ├── style.css          # 全站样式（深色主题）
│   ├── app.js             # 前端逻辑（路由、认证、数据管理）
│   └── config.js          # 前端配置（后端发现、本地用户数据库）
│
├── build/                 # 构建产物（单文件 index.html，可直接部署）
│
├── template/              # 任务模板（添加任务时复制）
│   ├── main.py            # 云运动核心（SM2/SM4 加密、API 请求）
│   ├── history_api.py     # 历史记录 API 脚本
│   ├── tools/Login.py     # 云运动登录模块
│   └── config.ini         # 模板配置文件
│
├── scripts/               # CLI 命令行工具
│   ├── task_manager.py    # 命令行任务管理
│   ├── run_yyd_tasks.sh   # 定时调度脚本
│   └── fetch_server_stats.py # 拉取跑步统计
│
├── tasks/                 # 各用户独立任务目录（JW*）
│   └── JW250102/          # 用户目录（config.ini, tasks_fch/ 等）
│
└── log/                   # 运行日志（JW*_日期_时间.log）
```

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/me` | GET | 当前用户信息 |
| `/api/auth/logout` | POST | 退出登录 |
| `/api/auth/change-password` | POST | 修改网页登录密码 |
| `/api/tasks` | GET/POST | 任务列表 / 添加任务 |
| `/api/tasks/<id>` | GET/PUT/DELETE | 单个任务 CRUD |
| `/api/tasks/<id>/yun-password` | POST | 修改云运动账号密码 |
| `/api/tasks/<id>/fetch` | POST | 拉取跑步统计数据 |
| `/api/tasks/<id>/reset` | POST | 重置统计 |
| `/api/tasks/<id>/history/terms` | POST | 获取学期列表 |
| `/api/tasks/<id>/history/runs` | POST | 获取跑步记录 |
| `/api/tasks/<id>/history/preview` | POST | 预览跑步详情（不保存） |
| `/api/tasks/<id>/history/save` | POST | 保存跑步记录 |
| `/api/tasks/<id>/delete-request` | POST | 提交删除申请 |
| `/api/delete-requests` | GET | 待审核列表（管理员） |
| `/api/delete-requests/<id>/approve` | POST | 批准删除 |
| `/api/delete-requests/<id>/reject` | POST | 拒绝删除 |
| `/api/delete-requests/my` | GET | 我的删除申请 |
| `/api/stats` | GET | 聚合统计 |
| `/api/logs` | GET | 运行日志（按学号分组） |
| `/api/logs/<sid>` | GET | 指定学号日志内容 |
| `/api/audit-logs` | GET | 操作审计日志 |
| `/api/contact` | GET/PUT | 我的联系方式 |
| `/api/contacts` | GET | 全部联系方式（管理员） |
| `/api/health` | GET | 健康检查 |
| `/api/discovery` | GET | 服务发现 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| PORT | 后端监听端口 | 5700 |
| CORS_ALLOWED | CORS 白名单（逗号分隔，`*` 全部放行） | 局域网自动放行 |

## 构建

```bash
python build.py   # 产出 build/index.html（单文件，可直接部署）
```

构建产物将 CSS、JS 全部内联到 HTML 中，只需要部署一个文件即可运行完整前端。
