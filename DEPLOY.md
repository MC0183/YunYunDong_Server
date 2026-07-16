# 多服务器部署说明

## 架构

```
┌─────────────┐     API 请求     ┌─────────────┐
│   前端       │ ────────────►  │   后端       │
│ (任意服务器)  │ ◄────────────  │ (Windows/Linux) │
│ nginx/OpenWRT│    CORS 响应   │ Flask :5700   │
└─────────────┘                 └─────────────┘
```

## 部署方式

### 1. 同机部署（最简单）
前端和后端在同一台机器上，不需要额外配置。
```bash
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:5700
```

### 2. 独立前端 + 后端

#### 后端服务器启动
```bash
# Linux/Mac
pip install -r requirements.txt
PORT=5700 CORS_ALLOWED="http://你的前端IP:端口" python server.py

# Windows (CMD)
set PORT=5700
set CORS_ALLOWED=http://你的前端IP:端口
python server.py

# Windows (PowerShell)
$env:PORT="5700"
$env:CORS_ALLOWED="http://你的前端IP:端口"
python server.py
```

环境变量：
| 变量 | 说明 | 默认值 |
|------|------|--------|
| PORT | 后端监听端口 | 5700 |
| CORS_ALLOWED | 允许的跨域来源，逗号分隔，支持通配符 | 局域网自动放行 |

#### 前端部署（静态文件）
只需要 `static/` 目录的文件，用任意 Web 服务器托管：

**nginx 配置示例：**
```nginx
server {
    listen 80;
    root /path/to/static;
    index index.html;
}
```

**修改 `static/config.js` 指向后端：**
```javascript
window.API_BASE = "http://192.168.1.100:5700";
```

**OpenWRT 路由器：** 将 `static/` 目录放到 `/www/tasks/`，安装 `uhttpd`，浏览器访问 `http://路由器IP/tasks/`。

### 3. 多后端 + 前端负载

启动多台后端服务器：
```bash
# 服务器A
PORT=5700 python server.py

# 服务器B
PORT=5700 python server.py
```

前端 `config.js` 指向某一台即可（所有后端共享 `data/` 目录）。

### 4. 健康检查
```bash
curl http://后端IP:5700/api/health
# {"status":"ok","time":"2026-07-17 05:30:00"}
```

## CORS 配置

后端自动放行以下来源（无需手动配置）：
- `localhost`、`127.0.0.1`
- `10.x.x.x`、`192.168.x.x`、`172.16-31.x.x`

如果需要放行公网域名，设置环境变量：
```bash
CORS_ALLOWED=https://你的域名:端口,https://另一个域名
# 或全部放行（仅限内网使用）：
CORS_ALLOWED=*
```

## 目录结构
```
project/
├── server.py          # 后端主程序
├── requirements.txt   # Python 依赖
├── start.bat          # Windows 一键启动
├── data/              # 数据文件（JSON）
├── static/            # 前端静态文件（独立部署时只需这个）
├── template/          # 任务模板
├── scripts/           # CLI 工具
├── tasks/             # 各用户任务目录
└── log/               # 运行日志
```
