#!/usr/bin/env python3
"""
从服务器获取指定任务的真实跑步数据
用法: python3 fetch_server_stats.py <config_path>
输出: JSON {"success": true/false, "total_runs": N, "total_km": N.N, "error": "..."}

工作流程：
  1. cd 到任务目录
  2. 加载 config.ini 初始化 main 模块全局变量
  3. 调用 /run/listXnYearXqByStudentId 获取学期列表
  4. 遍历每个学期调用 /run/crsReocordInfoList 获取跑步统计
  5. 输出 JSON 结果
"""
import json, sys, os, importlib

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "缺少 config_path 参数"}))
    sys.exit(1)

config_path = sys.argv[1]
if not os.path.exists(config_path):
    print(json.dumps({"success": False, "error": f"配置文件不存在: {config_path}"}))
    sys.exit(1)

task_dir = os.path.dirname(config_path)

# 切换到任务目录（main.py 依赖此行为）
os.chdir(task_dir)

# 添加路径，确保能从任务目录导入 main 和 tools
sys.path.insert(0, task_dir)
tools_dir = os.path.join(task_dir, 'tools')
if os.path.exists(tools_dir):
    sys.path.insert(0, tools_dir)

try:
    # 导入 main 模块，并通过 set_args 初始化所有全局变量
    import main
    importlib.reload(main)
    main.set_args(config_path)

    # 1. 获取学期列表
    term_json = main.default_post("/run/listXnYearXqByStudentId", data='')
    term_data = json.loads(term_json)

    if term_data.get("code") != 200:
        print(json.dumps({
            "success": False,
            "error": f"获取学期列表失败: {term_data.get('msg', '未知错误')}"
        }))
        sys.exit(1)

    terms = term_data.get("data", [])
    if not terms:
        print(json.dumps({"success": True, "total_runs": 0, "total_km": 0}))
        sys.exit(0)

    # 2. 遍历所有学期，累加跑步次数和公里数
    total_runs = 0
    total_km = 0.0
    runs_detail = []

    for term in terms:
        term_key = term.get("key", "")
        term_value = term.get("value", "")
        try:
            run_list_json = main.default_post(
                "/run/crsReocordInfoList",
                data=json.dumps({"tableName": term_value})
            )
            run_list = json.loads(run_list_json)

            if run_list.get("code") == 200:
                data = run_list.get("data", {})
                sum_number = int(data.get("sumNumber", 0))
                sum_km = float(data.get("sumKm", 0))
                total_runs += sum_number
                total_km += sum_km
                runs_detail.append({
                    "term": term_key,
                    "runs": sum_number,
                    "km": sum_km
                })
        except Exception as e:
            runs_detail.append({
                "term": term_key,
                "runs": 0,
                "km": 0,
                "error": str(e)
            })

    # 3. 输出结果
    print(json.dumps({
        "success": True,
        "total_runs": total_runs,
        "total_km": round(total_km, 2),
        "detail": runs_detail
    }))
    sys.exit(0)

except Exception as e:
    print(json.dumps({
        "success": False,
        "error": f"{type(e).__name__}: {str(e)}"
    }))
    sys.exit(1)
