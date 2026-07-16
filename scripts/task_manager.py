#!/usr/bin/env python3
import os, sys, json, random, configparser, argparse, shutil, subprocess, hashlib, time

# ================= 路径配置 =================
BASE_DIR = "/tasks"                      # 任务存放根目录（可按需修改）
TASKS_JSON = os.path.join(BASE_DIR, "tasks.json")
DEVICES_JSON = os.path.join(BASE_DIR, "devices.json")
PROJECT_SRC = "/tasks/yunForNewVersion" # 原始项目模板路径
FETCH_SCRIPT = os.path.join(BASE_DIR, "fetch_server_stats.py") # 服务端数据拉取脚本
# ============================================

def load_device_map():
    if not os.path.exists(DEVICES_JSON): return {}
    try:
        with open(DEVICES_JSON, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def load_tasks():
    if not os.path.exists(TASKS_JSON): return {"tasks": []}
    with open(TASKS_JSON, 'r', encoding='utf-8') as f: return json.load(f)

def save_tasks(data):
    with open(TASKS_JSON, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)

def add_task(username, password, school_name, skip_login=False):
    device_map = load_device_map()
    if not device_map:
        print("❌ 未找到 devices.json 或格式错误，无法分配设备信息。"); return

    if any(t['id'] == username for t in load_tasks()['tasks']):
        print(f"❌ 任务已存在: {username}"); return

    # 1. 创建任务目录 & 复制项目文件
    task_dir = os.path.join(BASE_DIR, username)
    os.makedirs(task_dir, exist_ok=True)
    if os.path.exists(PROJECT_SRC):
        print(f"📦 正在复制项目文件至 {task_dir}...")
        try:
            shutil.copytree(PROJECT_SRC, task_dir, dirs_exist_ok=True)
        except TypeError:
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir)
            shutil.copytree(PROJECT_SRC, task_dir)
    else:
        print(f"⚠️ 警告: 未找到模板目录 {PROJECT_SRC}，仅创建空目录与配置文件。")
        os.makedirs(os.path.join(task_dir, "tasks_fch"), exist_ok=True)

    # 随机分配设备
    device, os_ver = random.choice(list(device_map.items()))
    os_ver = random.choice(os_ver)

    # 2. 准备 config.ini 用于登录提取（必须包含 Login 模块运行所需的全部字段）
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
school_name = {school_name}

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
    with open(os.path.join(task_dir, "config.ini"), "w", encoding="utf-8") as f: f.write(tmp_cfg)

    # 3. 静默登录并提取凭证
    creds = {"token": "", "device_id": "", "device_name": device, "uuid": "", "sys_edition": os_ver}
    if not skip_login:
        print(f"🔍 正在验证 {username} 的凭据并提取凭证...")
        helper_script = os.path.join(task_dir, "_login_helper.py")
        
        # ✅ 修复：将 Login 的输出重定向到 stderr，确保 JSON 结果能正确输出到 stdout
        helper_code = """
import sys, os, json
task_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.join(task_dir, 'tools')

# 确保 tools 目录和任务根目录优先被搜索
if os.path.exists(tools_dir) and tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)
if task_dir not in sys.path:
    sys.path.insert(0, task_dir)

# 切换工作目录到任务根目录（与 main.py 行为保持一致）
os.chdir(task_dir)

try:
    from tools.Login import Login
    # 屏蔽 Login 内部的标准输出日志，防止污染 JSON 返回
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    res = Login.main()
    sys.stdout = old_stdout
    
    if res and len(res) >= 5:
        print(json.dumps({
            "token": res[0], 
            "device_id": res[1], 
            "device_name": res[2], 
            "uuid": res[3], 
            "sys_edition": res[4]
        }))
        sys.exit(0)
    else:
        print(json.dumps({"error": f"Login 返回格式异常: {res}"}))
        sys.exit(1)
except Exception as e:
    print(json.dumps({"error": f"{type(e).__name__}: {str(e)}"}))
    sys.exit(1)
"""
        with open(helper_script, "w", encoding="utf-8") as f: f.write(helper_code)

        try:
            result = subprocess.run(
                [sys.executable, helper_script], cwd=task_dir,
                capture_output=True, text=True, timeout=60
            )
            if os.path.exists(helper_script): os.remove(helper_script)

            out = result.stdout.strip()
            # ✅ 修复：安全解析 JSON，避免空字符串或非法格式导致崩溃
            if result.returncode == 0 and out:
              try:
                login_data = json.loads(out)
                creds['token'] = login_data.get('token', creds['token'])
                creds['device_id'] = login_data.get('device_id', creds['device_id'])
                creds['uuid'] = login_data.get('uuid', creds['uuid'])
                # device_name 和 sys_edition 保持随机值不变
                print("✅ 凭证提取成功。")
              except json.JSONDecodeError:
                print(f"⚠️ 解析登录结果失败，原始输出: {out[:100]}")
                if result.stderr.strip(): print(f"📜 调试日志:\n{result.stderr.strip()[-300:]}")
            else:
                err_msg = "未知错误"
                if out:
                    try: err_msg = json.loads(out).get("error", "登录脚本异常")
                    except: err_msg = f"非 JSON 异常输出: {out[:80]}"
                print(f"⚠️ 登录失败: {err_msg}")
                if result.stderr.strip():
                    print(f"📜 详细报错:\n{result.stderr.strip()[-500:]}")
                
                if not sys.stdin.isatty():
                    print("⛔ 非交互环境，登录失败时自动终止（使用 --skip-login 可跳过验证）")
                    shutil.rmtree(task_dir, ignore_errors=True)
                    return
                cont = input("是否使用空凭证继续创建任务？(y/n) [n]: ").strip().lower()
                if cont != "y":
                    print("⛔ 已取消添加，正在清理目录...")
                    shutil.rmtree(task_dir, ignore_errors=True)
                    return
        except subprocess.TimeoutExpired:
            print("⏱️ 登录请求超时 (60s)，跳过凭证提取。")
            if os.path.exists(helper_script): os.remove(helper_script)

        # 4. 生成完整 config.ini（已移除 PublicKey/PrivateKey 避免 configparser 大小写冲突）
    utc = str(int(time.time()))
    sign_raw = f"platform=android&utc={utc}&uuid={creds['uuid']}&appsecret=pie0hDSfMRINRXc7s1UIXfkE"
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
school_name = {school_name}

[User]
token = {creds['token']}
device_id = {creds['device_id']}
map_key =
device_name = {creds['device_name']}
utc = {utc}
uuid = {creds['uuid']}
sign = {sign}
sys_edition = {creds['sys_edition']}

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
    with open(os.path.join(task_dir, "config.ini"), 'w', encoding='utf-8') as f: f.write(full_cfg)

    # 5. 保存任务配置
    data = load_tasks()
    data['tasks'].append({
        "id": username, "username": username, "password": password,
        "school": school_name, "device_name": creds["device_name"], "sys_edition": creds["sys_edition"],
        "start_time": "06:00", "dir_path": task_dir,
        "enabled": True, "max_runs": None,
        "run_stats": {"total": 0, "success": 0, "fail": 0, "last_run": "", "last_status": ""}
    })
    save_tasks(data)
    print(f"✅ 成功添加任务: {username}")
    print(f"📁 目录: {task_dir}")
    print(f"📱 设备: {creds['device_name']} (Android {creds['sys_edition']})")
    if creds['token']:
        print(f"🔑 Token: {creds['token'][:10]}... (已写入 config.ini)")

def delete_task(task_id):
    data = load_tasks()
    task = next((t for t in data['tasks'] if t['id'] == task_id), None)
    if not task: print(f"❌ 未找到任务: {task_id}"); return
    if os.path.exists(task['dir_path']): shutil.rmtree(task['dir_path'])
    data['tasks'] = [t for t in data['tasks'] if t['id'] != task_id]
    save_tasks(data); print(f"🗑️ 已删除任务: {task_id}")

def set_start_time(task_id, new_time):
    try: time.strptime(new_time, "%H:%M")
    except ValueError: print("❌ 时间格式错误，请使用 HH:MM"); return
    data = load_tasks()
    for t in data['tasks']:
        if t['id'] == task_id:
            t['start_time'] = new_time; save_tasks(data)
            print(f"⏰ 任务 {task_id} 计划时间已设为: {new_time}"); return
    print(f"❌ 未找到任务: {task_id}")

def list_tasks():
    data = load_tasks()
    if not data['tasks']: print("📭 暂无任务。"); return
    print(f"{'ID':<12} {'学校':<20} {'计划时间':<8} {'启用':<6} {'脚本执行':<9} {'服务器记录':<10} {'最大运行':<9} {'最后状态':<10}")
    print("-" * 88)
    for t in data['tasks']:
        enabled = "✅" if t.get('enabled', True) else "❌"
        stats = t.get('run_stats', {})
        total = stats.get('total', 0)
        success = stats.get('success', 0)
        server_total = stats.get('server_total', '-')
        server_str = str(server_total) if isinstance(server_total, int) else "-"
        max_runs = t.get('max_runs')
        max_str = str(max_runs) if max_runs is not None else "无限制"
        last_status = stats.get('last_status', '')
        last_status_str = {"0": "成功", "1": "Token失效", "2": "成绩不合格", "3": "代码错误"}.get(str(last_status), last_status if last_status else "-")
        print(f"{t['id']:<12} {t['school']:<20} {t['start_time']:<8} {enabled:<6} {success:<4}/{total:<4} {server_str:<9} {max_str:<9} {last_status_str:<10}")

def set_enabled(task_id, enabled):
    data = load_tasks()
    for t in data['tasks']:
        if t['id'] == task_id:
            t['enabled'] = enabled
            save_tasks(data)
            status = "启用" if enabled else "禁用"
            print(f"✅ 任务 {task_id} 已{status}")
            return
    print(f"❌ 未找到任务: {task_id}")

def set_max_runs(task_id, max_runs):
    data = load_tasks()
    for t in data['tasks']:
        if t['id'] == task_id:
            t['max_runs'] = max_runs if max_runs > 0 else None
            save_tasks(data)
            if max_runs > 0:
                print(f"⏱️ 任务 {task_id} 最大运行次数已设为: {max_runs}（达到后自动禁用）")
            else:
                print(f"⏱️ 任务 {task_id} 已取消最大运行次数限制")
            return
    print(f"❌ 未找到任务: {task_id}")

def reset_stats(task_id):
    data = load_tasks()
    for t in data['tasks']:
        if t['id'] == task_id:
            t['run_stats'] = {"total": 0, "success": 0, "fail": 0, "last_run": "", "last_status": ""}
            save_tasks(data)
            print(f"🔄 任务 {task_id} 的运行统计已重置")
            return
    print(f"❌ 未找到任务: {task_id}")

def fetch_stats(task_id=None):
    """从服务器拉取任务的真实跑步次数"""
    data = load_tasks()
    if not data['tasks']:
        print("📭 暂无任务。")
        return
    
    targets = [t for t in data['tasks'] if task_id is None or t['id'] == task_id]
    if not targets:
        print(f"❌ 未找到任务: {task_id}")
        return
    
    script_path = FETCH_SCRIPT
    if not os.path.exists(script_path):
        print(f"❌ 未找到辅助脚本: {script_path}")
        return
    
    for t in targets:
        task_id = t['id']
        config_path = os.path.join(t['dir_path'], "config.ini")
        if not os.path.exists(config_path):
            print(f"⚠️ 跳过 {task_id}：config.ini 不存在")
            continue
        
        print(f"🔍 正在查询 {task_id}（{t.get('school', '')}）...", end=" ", flush=True)
        try:
            result = subprocess.run(
                [sys.executable, script_path, config_path],
                capture_output=True, text=True, timeout=30
            )
            out = result.stdout.strip()
            if not out:
                print(f"❌ 无输出 (stderr: {result.stderr.strip()[:100]})")
                continue
            
            resp = json.loads(out)
            if resp.get("success"):
                total_runs = resp["total_runs"]
                total_km = resp["total_km"]
                # 更新到 tasks.json
                stats = t.setdefault("run_stats", {})
                stats["server_total"] = total_runs
                stats["server_total_km"] = total_km
                stats["server_fetch_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                save_tasks(data)
                print(f"✅ 服务器记录: {total_runs} 次, {total_km} 公里")
            else:
                print(f"❌ {resp.get('error', '未知错误')}")
        except subprocess.TimeoutExpired:
            print(f"⏱️ 超时 (30s)")
        except json.JSONDecodeError:
            print(f"❌ 返回数据解析失败")
        except Exception as e:
            print(f"❌ {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    
    p_add = sub.add_parser("add")
    p_add.add_argument("user"); p_add.add_argument("password"); p_add.add_argument("school")
    p_add.add_argument("--skip-login", action="store_true", help="跳过登录验证，使用占位符创建")
    
    p_del = sub.add_parser("delete"); p_del.add_argument("id")
    p_time = sub.add_parser("set_time"); p_time.add_argument("id"); p_time.add_argument("time")
    sub.add_parser("list")
    
    p_enable = sub.add_parser("enable"); p_enable.add_argument("id")
    p_disable = sub.add_parser("disable"); p_disable.add_argument("id")
    p_max = sub.add_parser("set_max_runs"); p_max.add_argument("id"); p_max.add_argument("n", type=int)
    p_reset = sub.add_parser("reset_stats"); p_reset.add_argument("id")
    
    p_fetch = sub.add_parser("fetch_stats", help="从服务器拉取真实跑步次数（可指定任务ID，不指定则拉取全部）")
    p_fetch.add_argument("id", nargs="?", default=None, help="任务ID（可选，不指定则拉取全部）")
    
    args = parser.parse_args()
    cmds = {
        "add": lambda: add_task(args.user, args.password, args.school, args.skip_login),
        "delete": lambda: delete_task(args.id),
        "set_time": lambda: set_start_time(args.id, args.time),
        "list": list_tasks,
        "enable": lambda: set_enabled(args.id, True),
        "disable": lambda: set_enabled(args.id, False),
        "set_max_runs": lambda: set_max_runs(args.id, args.n),
        "reset_stats": lambda: reset_stats(args.id),
        "fetch_stats": lambda: fetch_stats(args.id),
    }
    if args.cmd in cmds:
        cmds[args.cmd]()
    else:
        parser.print_help()