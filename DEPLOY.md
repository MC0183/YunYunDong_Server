# 多服务器部署说明

## 架构

```
┌──────────────┐   API 请求    ┌──────────────┐
│  前端 (任意)   │ ────────────►│  后端 A       │
│  nginx/路由器  │ ◄──────────── │  Flask :5700  │
│  OpenWRT/静态 │              ├──────────────┤
│              │  自动切换      │  后端 B       │
│              │ ◄───────────► │  Flask :5700  │
└──────────────┘              └──────────────┘
```

## 部署方式

### 1. 同机部署（最简单）
```bash
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:5700
```

### 2. 前后端分离部署

#### 前端（纯静态文件，放哪里都行）

**方式 A — 构建单文件（推荐）：**
```bash
python build.py                            # 合并 CSS/JS 到 index.html
scp build/index.html root@路由器IP:/www/tasks/
# 浏览器打开 http://路由器IP/tasks/?api=http://后端IP:5700
```

**方式 B — 直接部署 static/ 目录：**
```bash
scp -r static/* root@路由器IP:/www/tasks/
```

首次访问时在 URL 后面加 `?api=http://后端IP:5700` 配对，成功后浏览器自动记住，后续无需再加。

💡 登录页 3 秒后自动提示后端配对方法。

#### 后端
```bash
PORT=5700 python server.py
```

环境变量：
| 变量 | 说明 | 默认值 |
|------|------|--------|
| PORT | 后端监听端口 | 5700 |
| CORS_ALLOWED | 后端监听端口 | 局域网自动放行 (10.x, 192.168.x, 172.16-31.x) |

### 3. 多后端聚合

管理后台 → 导航栏右上角 `📡 后端` → 添加多台后端地址：

```
http://10.0.0.121:5700
http://10.0.0.122:5700
```

前端自动从全部后端并行拉取任务数据并去重合并。前端自动从全部后端并行拉取任务数据并去重合并。

添加新任务时可选择存放后端。

### 4. 离线登录

前端 `localStorage` 中保存用户数据库：
- 管理员首次后端登录后，自动同步所有用户信息到本地
- 后续普通用户登录优先查本地数据库，**无需后端联网**
- 后端完全离线时仍可登录使用（显示缓存数据）

### 5. 健康检查

```bash
curl http://后端IP:5700/api/health
# {"status":"ok","time":"2026-07-18 10:00:00"}

curl http://后端IP:5700/api/discovery
# {"host":"10.0.0.121:5700","api_url":"http://10.0.0.121:5700","status":"ok"}
```

## CORS 配置

后端自动放行局域网来源（无需手动配置）：
- `localhost`, `127.0.0.1`
- `10.x.x.x`, `192.168.x.x`, `172.16-31.x.x`

公网域名手动设置：
```bash
CORS_ALLOWED=https://你的域名,https://另一个域名
# 全部放行（仅内网）：
CORS_ALLOWED=*
```

## 目录结构

```
project/
├── server.py          # Flask 后端主程序
├── build.py           # 构建单文件版前端
├── start.bat          # Windows 一键启动
├── requirements.txt   # Python 依赖
├── data/              # JSON 数据（tasks/users/audit/delete_requests/tokens）
├── static/            # 前端源文件（独立部署时可只用此目录或 build/ 产物）
│  ├── index.html, style.css, app.js, config.js
├── build/             # 构建产物（单文件 HTML，可直接部署）
├── template/          # 任务模板（添加任务时复制到此目录）
├── scripts/           # CLI 工具（task_manager.py, run_yyd_tasks.sh）
├── tasks/             # 各用户独立任务目录（JW*）
└── log/               # 运行日志
```

## 用户角色

| 角色 | 登录时 | 登录后 |
|------|--------|--------|
| **管理员** | 主后端认证失败 → 级联尝试其他后端 → 成功后同步所有用户到本地 | 看到全部任务，可管理多后端，可审核删除申请 |
| **普通用户** | 优先本地数据库（秒级）→ 后端验证补漏 | 只看自己的任务，可申请删除、查看消息 |
