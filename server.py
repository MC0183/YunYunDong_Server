#!/usr/bin/env python3
"""Task Management Web Server — 步道乐跑任务管理后台"""
import os, sys, json, subprocess, time, hashlib, random, secrets, re
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response

app = Flask(__name__, static_folder=None)

# ================= 路径配置 =================
BASE_DIR = Path(__file__).parent.resolve()
TASKS_JSON = BASE_DIR / "data" / "tasks.json"
DEVICES_JSON = BASE_DIR / "data" / "devices.json"
USERS_JSON = BASE_DIR / "data" / "users.json"
DELETE_REQUESTS_JSON = BASE_DIR / "data" / "delete_requests.json"
AUDIT_LOG_JSON = BASE_DIR / "data" / "audit_log.json"
TOKENS_JSON = BASE_DIR / "data" / "tokens.json"
FETCH_SCRIPT = BASE_DIR / "scripts" / "fetch_server_stats.py"
LOG_DIR = BASE_DIR / "log"

# ================= 鉴权 =================
def _load_tokens():
    """从磁盘加载持久化的 token"""
    if TOKENS_JSON.exists():
        try:
            return json.loads(TOKENS_JSON.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def _save_tokens(tokens):
    """将 token 持久化到磁盘"""
    TOKENS_JSON.write_text(json.dumps(tokens, ensure_ascii=False), encoding="utf-8")

_tokens = _load_tokens()  # token -> username，服务重启不丢失

def load_users():
    if not USERS_JSON.exists():
        return {"users": []}
    return json.loads(USERS_JSON.read_text(encoding="utf-8"))

def find_user(username, password):
    data = load_users()
    for u in data["users"]:
        if u["username"] == username and u["password"] == password:
            return u
    return None

def find_user_by_username(username):
    data = load_users()
    for u in data["users"]:
        if u["username"] == username:
            return u
    return None

def get_token_user(request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        username = _tokens.get(token)
        if username:
            return find_user_by_username(username)
    return None

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_token_user(request)
        if not user:
            return jsonify({"error": "未登录或登录已过期"}), 401
        request._user = user
        return f(*args, **kwargs)
    return wrapper

ALLOWED_ORIGINS = {"http://localhost:5700", "http://127.0.0.1:5700"}

# ================= 数据操作 =================
def load_tasks():
    if not TASKS_JSON.exists():
        return {"tasks": []}
    return json.loads(TASKS_JSON.read_text(encoding="utf-8"))

def save_tasks(data):
    TASKS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def load_devices():
    if not DEVICES_JSON.exists():
        return {}
    return json.loads(DEVICES_JSON.read_text(encoding="utf-8"))

def _get_task_or_404(task_id):
    """获取任务并检查权限，返回 (data, task, error_response)"""
    data = load_tasks()
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return data, None, (jsonify({"error": "任务不存在"}), 404)
    user = request._user
    if user["role"] != "admin" and task["id"] != user["username"]:
        return data, None, (jsonify({"error": "无权限"}), 403)
    return data, task, None

def _is_origin_allowed(origin):
    """检查 origin 是否允许。支持环境变量 CORS_ALLOWED 手动指定"""
    if not origin:
        return False
    # 1. 环境变量 CORS_ALLOWED（逗号分隔）
    allowed_env = os.environ.get("CORS_ALLOWED", "")
    if allowed_env:
        if allowed_env == "*":
            return True
        for a in [x.strip() for x in allowed_env.split(",")]:
            if origin == a or re.match(a.replace("*", ".*"), origin):
                return True
    # 2. 局域网/本地自动放行
    if re.match(r'^https?://(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[\:\:1\]|localhost)', origin):
        return True
    return False

# ================= API =================

@app.after_request
def add_cors(resp):
    origin = request.headers.get("Origin", "")
    if _is_origin_allowed(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return resp

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": time.strftime("%Y-%m-%d %H:%M:%S")})

@app.route("/api/discovery", methods=["GET"])
def discovery():
    """服务发现 — 返回当前节点信息，供前端自动连接"""
    host = request.host
    return jsonify({
        "host": host,
        "api_url": f"http://{host}",
        "status": "ok",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

# ---- 登录 ----
@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    body = request.get_json(silent=True) or {}
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    user = find_user(username, password)
    if not user:
        return jsonify({"error": "用户名或密码错误"}), 401
    token = secrets.token_hex(32)
    _tokens[token] = user["username"]
    _save_tokens(_tokens)
    _audit(user["username"], "登录")
    return jsonify({
        "token": token,
        "user": {"username": user["username"], "role": user["role"], "label": user.get("label", username)}
    })

@app.route("/api/auth/me", methods=["GET"])
@require_auth
def auth_me():
    u = request._user
    return jsonify({"username": u["username"], "role": u["role"], "label": u.get("label", u["username"])})

@app.route("/api/auth/logout", methods=["POST"])
@require_auth
def auth_logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        _tokens.pop(auth[7:], None)
        _save_tokens(_tokens)
    return jsonify({"message": "已退出"})

@app.route("/api/auth/change-password", methods=["POST"])
@require_auth
def auth_change_password():
    user = request._user
    body = request.get_json(silent=True) or {}
    new_password = body.get("new_password", "").strip()
    if not new_password:
        return jsonify({"error": "新密码不能为空"}), 400
    if len(new_password) < 4:
        return jsonify({"error": "密码至少4位"}), 400

    # 仅更新 users.json（网页登录密码）
    users_data = load_users()
    u = next((u for u in users_data["users"] if u["username"] == user["username"]), None)
    if u:
        u["password"] = new_password
        save_users(users_data)

    _audit(user["username"], "修改密码")
    return jsonify({"message": "网页登录密码修改成功"})

@app.route("/api/tasks/<task_id>/yun-password", methods=["POST"])
@require_auth
def update_yun_password(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403

    body = request.get_json(silent=True) or {}
    new_password = body.get("yun_password", "").strip()
    if not new_password:
        return jsonify({"error": "密码不能为空"}), 400
    if len(new_password) < 4:
        return jsonify({"error": "密码至少4位"}), 400

    # 1. 更新 tasks.json
    task["password"] = new_password
    save_tasks(data)

    # 2. 更新 config.ini
    config_path = Path(task["dir_path"]) / "config.ini"
    if config_path.exists():
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(str(config_path), encoding="utf-8")
        if cfg.has_section("Login"):
            cfg.set("Login", "password", new_password)
            with open(str(config_path), "w", encoding="utf-8") as f:
                cfg.write(f)

    _audit(user["username"], "修改云运动密码", f"任务 {task_id}")
    return jsonify({"message": "云运动密码修改成功"})

def save_users(data):
    USERS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

# ---- 联系方式 ----
CONTACT_TYPES = {"qq": "QQ", "wechat": "微信", "email": "邮箱", "phone": "电话"}
MAX_CONTACT_PER_TYPE = 5

def _clean_contact_list(items):
    """清理并限制联系方式列表为最多5个非空字符串"""
    if not isinstance(items, list):
        items = [str(items)] if items else []
    cleaned = [str(x).strip() for x in items if x and str(x).strip()]
    return cleaned[:MAX_CONTACT_PER_TYPE]

def _get_admin_contacts(data):
    """获取管理员的联系方式"""
    admin = next((u for u in data["users"] if u["role"] == "admin"), None)
    if admin:
        c = admin.get("contact", {})
        return {t: c.get(t, []) for t in CONTACT_TYPES}
    return {t: [] for t in CONTACT_TYPES}

@app.route("/api/contact", methods=["GET"])
@require_auth
def get_contact():
    user = request._user
    data = load_users()
    u = next((u for u in data["users"] if u["username"] == user["username"]), None)
    my_contact = {t: [] for t in CONTACT_TYPES}
    if u:
        c = u.get("contact", {})
        for t in CONTACT_TYPES:
            my_contact[t] = c.get(t, [])
    admin_contact = _get_admin_contacts(data)
    return jsonify({"mine": my_contact, "admin": admin_contact})

@app.route("/api/contact", methods=["PUT"])
@require_auth
def update_contact():
    user = request._user
    body = request.get_json(silent=True) or {}
    data = load_users()
    u = next((u for u in data["users"] if u["username"] == user["username"]), None)
    if not u:
        return jsonify({"error": "用户不存在"}), 404
    u.setdefault("contact", {})
    for t in CONTACT_TYPES:
        if t in body:
            items = body[t]
            if not isinstance(items, list):
                items = [items]
            cleaned = [str(x).strip()[:50] for x in items if x and str(x).strip()]
            if len(cleaned) > MAX_CONTACT_PER_TYPE:
                return jsonify({"error": f"{CONTACT_TYPES[t]}最多{MAX_CONTACT_PER_TYPE}个"}), 400
            u["contact"][t] = cleaned
    save_users(data)
    _audit(user["username"], "修改联系方式")
    return jsonify({"message": "联系方式已更新"})

@app.route("/api/contacts", methods=["GET"])
@require_auth
def list_contacts():
    user = request._user
    if user["role"] != "admin":
        return jsonify({"error": "仅管理员可查看"}), 403
    data = load_users()
    result = []
    for u in data["users"]:
        c = u.get("contact", {})
        entry = {"username": u["username"], "label": u.get("label", u["username"]), "role": u.get("role", "user")}
        for t in CONTACT_TYPES:
            entry[t] = c.get(t, [])
        result.append(entry)
    return jsonify({"contacts": result})

# ---- 操作日志 ----
def _audit(username, action, detail=""):
    """记录用户操作日志（追加写入，保留最近500条）"""
    log_entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "username": username, "action": action, "detail": detail}
    data = {"logs": []}
    if AUDIT_LOG_JSON.exists():
        try: data = json.loads(AUDIT_LOG_JSON.read_text(encoding="utf-8"))
        except: data = {"logs": []}
    data["logs"].append(log_entry)
    if len(data["logs"]) > 500:
        data["logs"] = data["logs"][-500:]
    AUDIT_LOG_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

@app.route("/api/audit-logs", methods=["GET"])
@require_auth
def get_audit_logs():
    user = request._user
    data = {"logs": []}
    if AUDIT_LOG_JSON.exists():
        try: data = json.loads(AUDIT_LOG_JSON.read_text(encoding="utf-8"))
        except: pass
    logs = data.get("logs", [])
    if user["role"] != "admin":
        logs = [l for l in logs if l.get("username") == user["username"]]
    # 倒序排列
    logs.reverse()
    return jsonify({"logs": logs})

def filter_tasks_for_user(user, tasks_list):
    """根据用户角色过滤任务列表"""
    if user["role"] == "admin":
        return tasks_list
    # 普通用户只看自己的学号
    return [t for t in tasks_list if t["id"] == user["username"]]

# ---- 删除请求 ----
def load_delete_requests():
    if not DELETE_REQUESTS_JSON.exists():
        return {"requests": []}
    return json.loads(DELETE_REQUESTS_JSON.read_text(encoding="utf-8"))

def save_delete_requests(data):
    DELETE_REQUESTS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

@app.route("/api/tasks/<task_id>/delete-request", methods=["POST"])
@require_auth
def submit_delete_request(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] == "admin":
        # 管理员直接删除
        import shutil
        task_dir = Path(task["dir_path"])
        if task_dir.exists():
            shutil.rmtree(str(task_dir))
        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
        save_tasks(data)
        return jsonify({"message": f"任务 {task_id} 已删除", "direct": True})
    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "").strip()
    reqs = load_delete_requests()
    # 检查是否有待处理的申请
    existing = [r for r in reqs["requests"] if r["task_id"] == task_id and r["status"] == "pending"]
    if existing:
        return jsonify({"error": "该任务已有待处理的删除申请"}), 409
    reqs["requests"].append({
        "id": secrets.token_hex(8),
        "task_id": task_id,
        "username": user["username"],
        "reason": reason or "未填写原因",
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resolved_at": "",
        "admin_response": ""
    })
    save_delete_requests(reqs)
    _audit(user["username"], "提交删除申请", f"任务 {task_id}: {reason}")
    return jsonify({"message": "删除申请已提交，等待管理员审核", "id": task_id}), 201

@app.route("/api/delete-requests", methods=["GET"])
@require_auth
def list_delete_requests():
    user = request._user
    if user["role"] != "admin":
        return jsonify({"error": "仅管理员可查看"}), 403
    reqs = load_delete_requests()
    # 补充任务名称
    data = load_tasks()
    for r in reqs["requests"]:
        task = next((t for t in data["tasks"] if t["id"] == r["task_id"]), None)
        r["task_exists"] = task is not None
    return jsonify(reqs)

@app.route("/api/delete-requests/<req_id>/approve", methods=["POST"])
@require_auth
def approve_delete_request(req_id):
    user = request._user
    if user["role"] != "admin":
        return jsonify({"error": "仅管理员可操作"}), 403
    reqs = load_delete_requests()
    req = next((r for r in reqs["requests"] if r["id"] == req_id), None)
    if not req:
        return jsonify({"error": "申请不存在"}), 404
    if req["status"] != "pending":
        return jsonify({"error": "该申请已处理"}), 400
    # 执行删除
    data = load_tasks()
    task = next((t for t in data["tasks"] if t["id"] == req["task_id"]), None)
    if task:
        import shutil
        task_dir = Path(task["dir_path"])
        if task_dir.exists():
            shutil.rmtree(str(task_dir))
        data["tasks"] = [t for t in data["tasks"] if t["id"] != req["task_id"]]
        save_tasks(data)
    req["status"] = "approved"
    req["resolved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    req["admin_response"] = "已批准"
    save_delete_requests(reqs)
    _audit(user["username"], "批准删除申请", f"任务 {req['task_id']} (申请人: {req['username']})")
    _audit(req['username'], "管理员操作", f"删除申请已通过")
    return jsonify({"message": f"已批准删除 {req['task_id']}"})

@app.route("/api/delete-requests/<req_id>/reject", methods=["POST"])
@require_auth
def reject_delete_request(req_id):
    user = request._user
    if user["role"] != "admin":
        return jsonify({"error": "仅管理员可操作"}), 403
    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "未给出理由")
    reqs = load_delete_requests()
    req = next((r for r in reqs["requests"] if r["id"] == req_id), None)
    if not req:
        return jsonify({"error": "申请不存在"}), 404
    if req["status"] != "pending":
        return jsonify({"error": "该申请已处理"}), 400
    req["status"] = "rejected"
    req["resolved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    req["admin_response"] = reason
    save_delete_requests(reqs)
    _audit(user["username"], "拒绝删除申请", f"任务 {req['task_id']} (申请人: {req['username']}): {reason}")
    _audit(req['username'], "管理员操作", f"删除申请已拒绝: {reason}")
    return jsonify({"message": f"已拒绝删除 {req['task_id']}"})

@app.route("/api/delete-requests/my", methods=["GET"])
@require_auth
def my_delete_requests():
    user = request._user
    reqs = load_delete_requests()
    mine = [r for r in reqs["requests"] if r["username"] == user["username"]]
    # 把待处理的排前面
    mine.sort(key=lambda r: (0 if r["status"] == "pending" else 1, r.get("created_at", "")), reverse=False)
    return jsonify({"requests": mine})

# ---- 任务列表 ----
@app.route("/api/tasks", methods=["GET"])
@require_auth
def get_tasks():
    data = load_tasks()
    user = request._user
    filtered = filter_tasks_for_user(user, data["tasks"])
    return jsonify({"tasks": filtered})

# ---- 单个任务详情 ----
@app.route("/api/tasks/<task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    return jsonify(task)

# ---- 添加任务 ----
def _verify_login(task_dir, username, password):
    """运行登录验证，返回 (creds_dict|None, error_msg)"""
    helper_script = task_dir / "_login_helper.py"
    helper_code = f"""
import sys, os, json
task_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.join(task_dir, 'tools')
if os.path.exists(tools_dir) and tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)
if task_dir not in sys.path:
    sys.path.insert(0, task_dir)
os.chdir(task_dir)
try:
    from tools.Login import Login
    old = sys.stdout
    sys.stdout = sys.stderr
    res = Login.main()
    sys.stdout = old
    if res and len(res) >= 5:
        print(json.dumps({{"token":res[0],"device_id":res[1],"device_name":res[2],"uuid":res[3],"sys_edition":res[4]}}))
        sys.exit(0)
    else:
        print(json.dumps({{"error":f"Login返回格式异常:{{res}}"}}))
        sys.exit(1)
except Exception as e:
    print(json.dumps({{"error":f"{{type(e).__name__}}:{{str(e)}}"}}))
    sys.exit(1)
"""
    helper_script.write_text(helper_code, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(helper_script)],
            cwd=str(task_dir), capture_output=True, text=True, timeout=15
        )
        out = result.stdout.strip()
        if result.returncode == 0 and out:
            try:
                creds = json.loads(out)
                if "token" in creds and "error" not in creds:
                    return creds, None
                return None, creds.get("error", "登录返回异常")
            except json.JSONDecodeError:
                return None, f"解析登录结果失败: {out[:100]}"
        else:
            err = "登录脚本异常"
            if out:
                try:
                    err = json.loads(out).get("error", "未知错误")
                except json.JSONDecodeError:
                    err = f"非JSON输出: {out[:80]}"
            return None, err
    except subprocess.TimeoutExpired:
        return None, "登录请求超时 (60s)"
    finally:
        if helper_script.exists():
            helper_script.unlink()


@app.route("/api/tasks", methods=["POST"])
@require_auth
def add_task():
    body = request.get_json(silent=True) or {}
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    school = body.get("school", "安徽邮电职业技术学院")

    # 普通用户只能创建自己的任务
    user = request._user
    if user["role"] != "admin" and username != user["username"]:
        return jsonify({"error": "无权限创建其他用户的任务"}), 403

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    data = load_tasks()
    if any(t["id"] == username for t in data["tasks"]):
        return jsonify({"error": f"任务 {username} 已存在"}), 409

    # 创建任务目录 & 复制项目文件
    task_dir = BASE_DIR / "tasks" / username
    task_dir.mkdir(exist_ok=True)
    project_src = BASE_DIR / "template"
    if project_src.exists():
        import shutil
        try:
            shutil.copytree(str(project_src), str(task_dir), dirs_exist_ok=True)
        except TypeError:
            if task_dir.exists():
                shutil.rmtree(str(task_dir))
            shutil.copytree(str(project_src), str(task_dir))
    else:
        (task_dir / "tasks_fch").mkdir(exist_ok=True)

    # 随机分配设备
    device_map = load_devices()
    device = "Unknown"
    os_ver = "15"
    if device_map:
        device, os_ver = random.choice(list(device_map.items()))
        os_ver = random.choice(os_ver)

    # 生成临时 config.ini 用于登录
    tmp_cfg = f"""[Yun]
school_host = https://sports.aiyyd.com:8000
publickey = BDdKFsuBf51UObke1pEgfER17biBg/5r8slqE4s8oOa8lVesWgIUxsRc+AmZ72GcuJ56f7avnyJe3CJY4n00LU4=
yun_host = http://47.99.163.239:8080
platform = android
app_edition = 3.5.10
school_login_url = appLogin
school_id = 195
md5key = pie0hDSfMRINRXc7s1UIXfkE
privatekey = P3s0+rMuY4Nt5cUWuOCjMhDzVNdom+W0RvdV6ngM+/E=
cipherkeyencrypted = BGfbsG9EkXz5KeCva8E0MisBeS6bhBEDId3VXeIuBoiBMZU0Mosv7PqKsvqxZ3PjkUlsjzh09Se629SWW45XP4TIUeXoLpYzgk5fAMbg0VNVnXuLH9xVzdHAeM+1qJrgvwwkwio85/DnrP1aArvVQrw3N4xd5tugqQ==
cipherkey = JXhWGZjmhhXN+nt8nLpNxA==
school_name = {school}

[User]
token =
device_id =
uuid =
device_name = {device}
sys_edition = {os_ver}
utc =
sign =
map_key =

[Login]
username = {username}
password = {password}
"""
    (task_dir / "config.ini").write_text(tmp_cfg, encoding="utf-8")

    # 验证登录
    creds, err = _verify_login(task_dir, username, password)
    if err:
        import shutil
        shutil.rmtree(str(task_dir), ignore_errors=True)
        return jsonify({"error": f"登录验证失败: {err}"}), 400

    # 登录成功，生成完整 config.ini
    utc_val = str(int(time.time()))
    sign_raw = f"platform=android&utc={utc_val}&uuid={creds.get('uuid','')}&appsecret=pie0hDSfMRINRXc7s1UIXfkE"
    try:
        sign = hashlib.md5(sign_raw.encode()).hexdigest()
    except ValueError:
        sign = hashlib.md5(sign_raw.encode(), usedforsecurity=False).hexdigest()

    full_cfg = f"""[Yun]
yun_host = http://47.99.163.239:8080
school_host = https://sports.aiyyd.com:8000
publickey = BDdKFsuBf51UObke1pEgfER17biBg/5r8slqE4s8oOa8lVesWgIUxsRc+AmZ72GcuJ56f7avnyJe3CJY4n00LU4=
privatekey = P3s0+rMuY4Nt5cUWuOCjMhDzVNdom+W0RvdV6ngM+/E=
cipherkeyencrypted = BGfbsG9EkXz5KeCva8E0MisBeS6bhBEDId3VXeIuBoiBMZU0Mosv7PqKsvqxZ3PjkUlsjzh09Se629SWW45XP4TIUeXoLpYzgk5fAMbg0VNVnXuLH9xVzdHAeM+1qJrgvwwkwio85/DnrP1aArvVQrw3N4xd5tugqQ==
cipherkey = JXhWGZjmhhXN+nt8nLpNxA==
md5key = pie0hDSfMRINRXc7s1UIXfkE
platform = android
app_edition = 3.5.10
school_login_url = appLogin
school_id = 195
school_name = {school}

[User]
token = {creds.get('token','')}
device_id = {creds.get('device_id','')}
map_key =
device_name = {creds.get('device_name',device)}
utc = {utc_val}
uuid = {creds.get('uuid','')}
sign = {sign}
sys_edition = {creds.get('sys_edition',os_ver)}

[Run]
exclude_points = ["117.209175,31.774432","117.208173,31.774737","117.208326,31.774448","117.206983,31.774748"]
min_distance = 2.5
allow_overflow_distance = 0.1
single_mileage_min_offset = 0.5
single_mileage_max_offset = -0.5
cadence_min_offset = 30
cadence_max_offset = -150
split_count = 10
min_consume = 4.50
max_consume = 5.50
strides = 0.8

[Login]
username = {username}
password = {password}
"""
    (task_dir / "config.ini").write_text(full_cfg, encoding="utf-8")

    # 保存任务
    data["tasks"].append({
        "id": username, "username": username, "password": password,
        "school": school, "device_name": creds.get("device_name", device),
        "sys_edition": creds.get("sys_edition", os_ver),
        "start_time": "06:00", "dir_path": str(task_dir),
        "enabled": True, "max_runs": None,
        "run_stats": {"total": 0, "success": 0, "fail": 0, "last_run": "", "last_status": ""}
    })
    save_tasks(data)
    return jsonify({"message": f"任务 {username} 添加成功", "id": username}), 201

# ---- 删除任务 ----
@app.route("/api/tasks/<task_id>", methods=["DELETE"])
@require_auth
def delete_task(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    import shutil
    task_dir = Path(task["dir_path"])
    if task_dir.exists():
        shutil.rmtree(str(task_dir))
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    save_tasks(data)
    return jsonify({"message": f"任务 {task_id} 已删除"})

# ---- 更新任务 ----
@app.route("/api/tasks/<task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    body = request.get_json(silent=True) or {}
    # 管理员禁用/启用 设置 disabled_by_admin 标记
    if "enabled" in body:
        if user["role"] == "admin":
            task["disabled_by_admin"] = not bool(body["enabled"])
            task["enabled"] = bool(body["enabled"])
        else:
            # 普通用户尝试启用时，检查是否被管理员禁用
            if body["enabled"] and task.get("disabled_by_admin"):
                return jsonify({"error": "管理员已禁用此账号，请向管理员咨询具体原因", "disabled_by_admin": True}), 403
            task["enabled"] = bool(body["enabled"])
    if "start_time" in body:
        task["start_time"] = body["start_time"]
    if "max_runs" in body:
        val = body["max_runs"]
        task["max_runs"] = val if isinstance(val, int) and val > 0 else None
    if "password" in body and body["password"]:
        task["password"] = body["password"]
    save_tasks(data)
    # 记录变更详情
    changes = []
    if "start_time" in body: changes.append(f"时间→{body['start_time']}")
    if "enabled" in body: changes.append(f"{'启用' if body['enabled'] else '禁用'}")
    if "max_runs" in body: changes.append(f"最大次数→{body['max_runs']}")
    if "password" in body and body["password"]: changes.append("修改密码")
    detail = "、".join(changes) if changes else "更新配置"
    _audit(request._user["username"], "修改任务", f"任务 {task_id}: {detail}")
    if request._user["role"] == "admin" and task_id != request._user["username"]:
        _audit(task_id, "管理员操作", f"修改任务: {detail}")
    return jsonify({"message": f"任务 {task_id} 已更新"})

# ---- 重置统计 ----
@app.route("/api/tasks/<task_id>/reset", methods=["POST"])
@require_auth
def reset_stats(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    task["run_stats"] = {"total": 0, "success": 0, "fail": 0, "last_run": "", "last_status": ""}
    save_tasks(data)
    _audit(request._user["username"], "重置统计", f"任务 {task_id}")
    if request._user["role"] == "admin" and task_id != request._user["username"]:
        _audit(task_id, "管理员操作", f"重置统计")
    return jsonify({"message": f"任务 {task_id} 统计已重置"})

# ---- 拉取服务器数据 ----
@app.route("/api/tasks/<task_id>/fetch", methods=["POST"])
@require_auth
def fetch_stats(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    config_path = Path(task["dir_path"]) / "config.ini"
    if not config_path.exists():
        return jsonify({"error": "config.ini 不存在"}), 400
    if not FETCH_SCRIPT.exists():
        return jsonify({"error": "fetch_server_stats.py 不存在"}), 500
    try:
        result = subprocess.run(
            [sys.executable, str(FETCH_SCRIPT), str(config_path)],
            capture_output=True, text=True, timeout=30
        )
        out = result.stdout.strip()
        if not out:
            return jsonify({"error": f"脚本无输出"}), 502
        resp = json.loads(out)
        if resp.get("success"):
            stats = task.setdefault("run_stats", {})
            stats["server_total"] = resp["total_runs"]
            stats["server_total_km"] = resp["total_km"]
            stats["server_fetch_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_tasks(data)
            _audit(request._user["username"], "拉取服务器数据", f"任务 {task_id}: {resp['total_runs']}次 {resp['total_km']}km")
            if request._user["role"] == "admin" and task_id != request._user["username"]:
                _audit(task_id, "管理员操作", f"拉取服务器数据: {resp['total_runs']}次 {resp['total_km']}km")
            return jsonify(resp)
        return jsonify({"error": resp.get("error", "拉取失败")}), 502
    except subprocess.TimeoutExpired:
        return jsonify({"error": "请求超时"}), 504
    except json.JSONDecodeError:
        return jsonify({"error": "返回数据解析失败"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- 拉取全部 ---- (admin only)
@app.route("/api/tasks/fetch-all", methods=["POST"])
@require_auth
def fetch_all_stats():
    user = request._user
    if user["role"] != "admin":
        return jsonify({"error": "仅管理员可批量拉取"}), 403
    data = load_tasks()
    results = []
    for t in data["tasks"]:
        config_path = Path(t["dir_path"]) / "config.ini"
        if not config_path.exists():
            results.append({"id": t["id"], "status": "skip", "reason": "无 config.ini"})
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(FETCH_SCRIPT), str(config_path)],
                capture_output=True, text=True, timeout=30
            )
            out = result.stdout.strip()
            if out:
                resp = json.loads(out)
                if resp.get("success"):
                    stats = t.setdefault("run_stats", {})
                    stats["server_total"] = resp["total_runs"]
                    stats["server_total_km"] = resp["total_km"]
                    stats["server_fetch_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    results.append({"id": t["id"], "status": "ok", "runs": resp["total_runs"], "km": resp["total_km"]})
                    continue
            results.append({"id": t["id"], "status": "error", "reason": out[:100] if out else "无输出"})
        except subprocess.TimeoutExpired:
            results.append({"id": t["id"], "status": "timeout"})
        except Exception as e:
            results.append({"id": t["id"], "status": "error", "reason": str(e)})
    save_tasks(data)
    ok = sum(1 for r in results if r.get("status") == "ok")
    fail = sum(1 for r in results if r.get("status") != "ok")
    _audit(request._user["username"], "批量拉取", f"{ok}成功 {fail}失败")
    return jsonify({"results": results})

# ---- 聚合统计 ----
@app.route("/api/stats", methods=["GET"])
@require_auth
def aggregate_stats():
    data = load_tasks()
    user = request._user
    tasks = filter_tasks_for_user(user, data["tasks"])
    total = len(tasks)
    enabled = sum(1 for t in tasks if t.get("enabled", True))
    disabled = total - enabled
    sum_success = sum(t.get("run_stats", {}).get("success", 0) for t in tasks)
    sum_fail = sum(t.get("run_stats", {}).get("fail", 0) for t in tasks)
    sum_server = sum(t.get("run_stats", {}).get("server_total", 0) for t in tasks if isinstance(t.get("run_stats", {}).get("server_total"), int))
    sum_km = sum(t.get("run_stats", {}).get("server_total_km", 0.0) for t in tasks if isinstance(t.get("run_stats", {}).get("server_total_km"), (int, float)))
    return jsonify({
        "total_tasks": total,
        "enabled": enabled,
        "disabled": disabled,
        "total_runs_local": sum_success + sum_fail,
        "total_success": sum_success,
        "total_fail": sum_fail,
        "server_total_runs": sum_server,
        "server_total_km": round(sum_km, 2),
        "schools": list({t.get("school", "未知") for t in tasks})
    })

# ---- 历史记录（history.py 功能）----
def _run_history_script(task_dir, *args):
    """运行 history_api.py 并返回 JSON"""
    task_path = Path(str(task_dir))
    script = task_path / "history_api.py"
    template = BASE_DIR / "template" / "history_api.py"
    if template.exists():
        import shutil
        shutil.copy2(str(template), str(script))
    if not script.exists():
        return {"error": "history_api.py 不存在"}
    try:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=str(task_dir), capture_output=True, text=True, timeout=30
        )
        out = result.stdout.strip()
        if out:
            return json.loads(out)
        return {"error": f"脚本无输出 (stderr: {result.stderr.strip()[:100]})"}
    except subprocess.TimeoutExpired:
        return {"error": "请求超时"}
    except json.JSONDecodeError:
        return {"error": "返回数据解析失败"}
    except Exception as e:
        return {"error": str(e)}

@app.route("/api/tasks/<task_id>/history/terms", methods=["POST"])
@require_auth
def history_terms(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    result = _run_history_script(task["dir_path"], "terms")
    if "error" in result:
        return jsonify(result), 502
    return jsonify(result)

@app.route("/api/tasks/<task_id>/history/runs", methods=["POST"])
@require_auth
def history_runs(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    body = request.get_json(silent=True) or {}
    table_name = body.get("tableName", "")
    if not table_name:
        return jsonify({"error": "缺少 tableName"}), 400
    result = _run_history_script(task["dir_path"], "runs", table_name)
    if "error" in result:
        return jsonify(result), 502
    return jsonify(result)

@app.route("/api/tasks/<task_id>/history/preview", methods=["POST"])
@require_auth
def history_preview(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    body = request.get_json(silent=True) or {}
    table_name = body.get("tableName", "")
    run_id = body.get("runId", "")
    if not table_name or not run_id:
        return jsonify({"error": "缺少 tableName 或 runId"}), 400
    result = _run_history_script(task["dir_path"], "preview", table_name, run_id)
    if "error" in result:
        return jsonify(result), 502
    return jsonify(result)

@app.route("/api/tasks/<task_id>/history/save", methods=["POST"])
@require_auth
def history_save(task_id):
    data = load_tasks()
    user = request._user
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if user["role"] != "admin" and task["id"] != user["username"]:
        return jsonify({"error": "无权限"}), 403
    body = request.get_json(silent=True) or {}
    table_name = body.get("tableName", "")
    run_id = body.get("runId", "")
    if not table_name or not run_id:
        return jsonify({"error": "缺少 tableName 或 runId"}), 400
    result = _run_history_script(task["dir_path"], "save", table_name, run_id)
    if "error" in result:
        return jsonify(result), 502
    if result.get("saved"):
        _audit(request._user["username"], "导入历史记录", f"任务 {task_id}")
        if request._user["role"] == "admin" and task_id != request._user["username"]:
            _audit(task_id, "管理员操作", f"导入历史记录")
    return jsonify(result)

@app.route("/api/logs", methods=["GET"])
@require_auth
def get_logs():
    user = request._user
    if not LOG_DIR.exists():
        return jsonify({"groups": []})
    log_files = sorted(LOG_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    groups = {}
    for f in log_files:
        if not f.is_file() or f.suffix != ".log":
            continue
        sid = f.name.split("_")[0]
        # 普通用户只看自己的日志
        if user["role"] != "admin" and sid != user["username"]:
            continue
        if sid not in groups:
            groups[sid] = []
        groups[sid].append({
            "name": f.name,
            "size": f.stat().st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime)),
        })
    # 排序：每组内按时间倒序，组间按学号
    for sid in groups:
        groups[sid].sort(key=lambda x: x["mtime"], reverse=True)
    sorted_groups = dict(sorted(groups.items()))
    return jsonify({"groups": sorted_groups})

@app.route("/api/logs/<sid>", methods=["GET"])
@require_auth
def get_student_log(sid):
    user = request._user
    if user["role"] != "admin" and sid != user["username"]:
        return jsonify({"error": "无权限"}), 403
    if not LOG_DIR.exists():
        return jsonify({"logs": []})
    log_files = sorted(LOG_DIR.glob(f"{sid}_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
    logs = []
    for f in log_files:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        logs.append({
            "name": f.name,
            "size": f.stat().st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime)),
            "content": "\n".join(lines),
        })
    return jsonify({"logs": logs})

# ---- 服务静态文件 ----
@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR / "static"), "index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(BASE_DIR / "static"), filename)

# ================= 启动 =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5700))
    print(f"🚀 任务管理后台启动: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
