# 本项目文件说明

## 根目录
| 文件 | 作用 |
|------|------|
| `server.py` | Flask Web 后端主程序，提供所有 REST API，服务运行中修改自动重载 |
| `start.bat` | Windows 一键安装依赖 + 启动服务器 |
| `requirements.txt` | Python 依赖清单（Flask、gmssl 等） |
| `DEPLOY.md` | 前后端分离部署文档（多服务器、OpenWRT） |

## data/ — 数据存储
| 文件 | 作用 |
|------|------|
| `tasks.json` | 所有用户任务的配置（账号、密码、学校、设备、计划时间、运行统计） |
| `users.json` | 所有用户的登录信息（用户名、密码、角色、联系方式） |
| `devices.json` | 设备池（添加任务时随机分配设备型号和 Android 版本） |
| `delete_requests.json` | 用户提交的删除申请（状态：pending/approved/rejected） |
| `audit_log.json` | 操作日志（登录、修改密码、启用/禁用任务等，保留最近 500 条） |
| `tokens.json` | 用户登录 Token 持久化（服务重启后 Token 不丢失） |

## scripts/ — CLI 命令行工具
| 文件 | 作用 |
|------|------|
| `task_manager.py` | 任务管理 CLI（add/delete/set_time/list/enable/disable/fetch_stats） |
| `run_yyd_tasks.sh` | 定时调度脚本（到指定时间依次运行每个任务） |
| `fetch_server_stats.py` | 从云运动服务器拉取跑步次数和里程数据 |
| `流程.txt` | 系统协作流程说明文档 |

## static/ — 前端 Web 界面
| 文件 | 作用 |
|------|------|
| `index.html` | 主页面（导航栏、登录页、各功能页面的弹窗模板） |
| `style.css` | 全部样式（深色主题、响应式布局、颜色变量） |
| `app.js` | 前端逻辑（路由、鉴权、任务管理、日志查看、历史记录、消息等） |
| `config.js` | 前端配置（自动发现后端地址，支持 localStorage 记忆和 URL 参数配对） |

## template/ — 任务模板
| 文件 | 作用 |
|------|------|
| `history_api.py` | 历史记录 API 脚本（获取学期/跑步记录/详情，被 server.py 的 subprocess 调用） |
| `history.py` | 原始历史记录提取工具（交互式命令行版，含 SM4 解密逻辑） |
| `main.py` | 云运动核心模块（default_post、加密解密、SM2/SM4、Login 集成） |
| `tools/Login.py` | 云运动登录模块（从 config.ini 读取凭据，返回 token/device_id/uuid） |
| `tools/` | 其他工具类（pace_changer、proxy、drift 等） |
| `tasks_fch/` | 任务文件存储目录（history_api.py 将导入的历史记录保存到此） |
| `config.ini` | 模板配置文件（新任务创建时以此为模板，再填充实际数据） |

## tasks/ — 各用户任务目录
| 文件 | 作用 |
|------|------|
| `XXXXXXXX(学号)/` 等 | 每个用户的独立任务目录（以学号命名） |
| `config.ini` | 该用户的云运动配置（token、device_id、学校、Login 凭据） |
| `main.py` | 云运动核心模块副本（从template复制） |
| `tools/Login.py` | 登录模块副本 |
| `tasks_fch/tasklist_*.json` | 该用户的跑步任务列表文件 |
| `history_api.py` | 历史记录 API 脚本副本（首次调用时从template复制） |

## log/ — 运行日志
| 文件 | 作用 |
|------|------|
| `XXXXXXXXX(学号)_XXXXXXXX(日期)_XXXXXX(时间).log` 等 | 每个用户每次运行的日志 |
| `main_cron.log` | 定时调度主日志 |
