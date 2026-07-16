#!/usr/bin/env python3
"""历史记录API — 被 server.py 以 subprocess 调用的非交互式版本"""
import sys, os, json, base64, gzip, time

# 切换到任务目录
task_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(task_dir)
sys.path.insert(0, task_dir)
sys.path.insert(0, os.path.join(task_dir, 'tools'))

from tools.Login import Login
from base64 import b64decode
from gmssl.sm4 import CryptSM4, SM4_DECRYPT

# 导入 main 模块并初始化配置
import importlib.util
spec = importlib.util.spec_from_file_location("main_mod", os.path.join(task_dir, "main.py"))
main = importlib.util.module_from_spec(spec)
sys.modules['main'] = main
spec.loader.exec_module(main)

# 读取 config.ini 初始化全局变量
conf_path = os.path.join(task_dir, "config.ini")
main.set_args(conf_path)

# 从 main 模块引入需要用到的全局变量和函数
default_post = main.default_post
my_host = main.my_host
my_token = main.my_token
my_device_id = main.my_device_id
my_device_name = main.my_device_name
my_uuid = main.my_uuid
my_app_edition = main.my_app_edition

def cmd_terms():
    """获取学期列表"""
    try:
        resp = default_post("/run/listXnYearXqByStudentId", data='')
        data = json.loads(resp)
        if data.get("code") != 200:
            print(json.dumps({"error": data.get("msg", "获取失败")}))
            return
        terms = data.get("data", [])
        print(json.dumps({"terms": [
            {"key": t["key"], "value": t["value"], "sjd": t.get("sjd", "")}
            for t in terms
        ]}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

def cmd_runs(table_name):
    """获取某学期的跑步记录列表"""
    try:
        resp = default_post("/run/crsReocordInfoList",
                           data=json.dumps({"tableName": table_name}))
        data = json.loads(resp)
        if data.get("code") != 200:
            print(json.dumps({"error": data.get("msg", "获取失败")}))
            return
        all_runs = []
        for month_data in data.get("data", {}).get("rank", []):
            for run in month_data.get("rankList", []):
                all_runs.append({
                    "id": run["id"],
                    "endTime": run.get("endTime", ""),
                    "recordMileage": run.get("recordMileage", "0"),
                })
        print(json.dumps({"runs": all_runs}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

def cmd_preview(table_name, run_id):
    """获取详细记录但不保存"""
    try:
        key_ctx = {}
        resp = default_post("/run/crsReocordInfo",
                           data=json.dumps({"id": run_id, "tableName": table_name}),
                           key_ctx=key_ctx)
        key = b64decode(key_ctx["key"])
        text = gzip.decompress(decrypt_sm4(resp, key)).decode()
        detail = json.loads(text)
        if detail.get("code") != 200:
            print(json.dumps({"error": detail.get("msg", "获取失败")}))
            return
        data = detail.get("data", {})
        print(json.dumps({
            "success": True,
            "saved": False,
            "summary": {
                "recordStartTime": data.get("recordStartTime", ""),
                "recordEndTime": data.get("recordEndTime", ""),
                "recordMileage": data.get("recordMileage", "0"),
                "recodePace": data.get("recodePace", "0"),
                "recodeCadence": data.get("recodeCadence", "0"),
                "duration": data.get("duration", "0"),
                "points": len(data.get("pointsList", [])),
            }
        }))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

def cmd_save(table_name, run_id):
    """获取并保存跑步详细记录到 tasks_fch"""
    try:
        key_ctx = {}
        resp = default_post("/run/crsReocordInfo",
                           data=json.dumps({"id": run_id, "tableName": table_name}),
                           key_ctx=key_ctx)
        key = b64decode(key_ctx["key"])
        text = gzip.decompress(decrypt_sm4(resp, key)).decode()
        detail = json.loads(text)
        if detail.get("code") != 200:
            print(json.dumps({"error": detail.get("msg", "获取失败")}))
            return

        tasks_fch = os.path.join(task_dir, "tasks_fch")
        os.makedirs(tasks_fch, exist_ok=True)
        files = [f for f in os.listdir(tasks_fch) if f.startswith("tasklist_") and f.endswith(".json")]
        last = 0
        for f in files:
            try:
                num = int(f.replace("tasklist_", "").replace(".json", ""))
                last = max(last, num + 1)
            except: pass
        target = os.path.join(tasks_fch, f"tasklist_{last}.json")
        with open(target, "w", encoding="utf-8") as f:
            f.write(text)

        print(json.dumps({"success": True, "saved": True, "path": target}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

def decrypt_sm4(ciphertext_b64, key_bytes):
    """SM4 解密"""
    cipher = CryptSM4()
    cipher.set_key(key_bytes, SM4_DECRYPT)
    raw = b64decode(ciphertext_b64)
    return cipher.crypt_ecb(raw)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "缺少命令"}))
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "terms":
        cmd_terms()
    elif cmd == "runs" and len(sys.argv) >= 3:
        cmd_runs(sys.argv[2])
    elif cmd == "preview" and len(sys.argv) >= 4:
        cmd_preview(sys.argv[2], sys.argv[3])
    elif cmd == "save" and len(sys.argv) >= 4:
        cmd_save(sys.argv[2], sys.argv[3])
    else:
        print(json.dumps({"error": f"未知命令: {cmd}"}))
        sys.exit(1)
