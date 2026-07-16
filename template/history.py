import json
import os
os.chdir(os.path.dirname(__file__))
import sys
import time
from main import * # 推荐import main，这种方式有很多全局变量问题，不推荐，但是事已至此不改了

def print_header():
    print("=" * 50)
    print("云运动历史记录提取工具")
    print("=" * 50)
    print("该工具将获取您的历史跑步记录，并保存为任务文件\n")

def select_option(options, title="请选择一个选项", show_indexes=True, per_page=10):
    if not options:
        print("没有可选项")
        return None
    
    total_pages = (len(options) + per_page - 1) // per_page
    current_page = 1
    
    while True:
        print(f"\n{title} (第{current_page}/{total_pages}页):")
        start_idx = (current_page - 1) * per_page
        end_idx = min(start_idx + per_page, len(options))
        
        for i in range(start_idx, end_idx):
            prefix = f"[{i+1}] " if show_indexes else ""
            print(f"{prefix}{options[i]}")
        
        if total_pages > 1:
            print("\n导航: [n]下一页 [p]上一页", end="")
        
        print(" [q]退出")
        
        choice = input("请输入选项编号: ").strip().lower()
        
        if choice == 'q':
            return None
        elif choice == 'n' and current_page < total_pages:
            current_page += 1
            continue
        elif choice == 'p' and current_page > 1:
            current_page -= 1
            continue
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
            else:
                print("无效的选择，请重试")
        except ValueError:
            print("请输入有效的数字")

def save_history_record(text, history_path):
    """保存历史记录到指定路径"""
    os.makedirs(history_path, exist_ok=True)
    
    files = os.listdir(history_path)
    last = 0
    
    # 找出最后一个文件编号
    for file in files:
        if file.startswith("tasklist_") and file.endswith(".json"):
            try:
                num = int(file.replace("tasklist_", "").replace(".json", ""))
                last = max(last, num + 1)
            except:
                pass
                
    target = os.path.join(history_path, f"tasklist_{last}.json")
    
    with open(file=target, mode='w+', encoding="utf-8") as f:
        print(f"保存记录到: {target}")
        f.write(text)
        f.flush()
    
    return target

def format_run_info(run):
    """格式化跑步信息为可读字符串"""
    end_time = run.get("endTime", "")
    record_mileage = run.get("recordMileage", "0")
    # recode_pace = run.get("recodePace", "0") # server这里有bug，返回的是0
    # recode_cadence = run.get("recodeCadence", "0")
    # duration = run.get("duration", "0")
    
    return f"{end_time} | {record_mileage}公里"

def his(args = None):
    print_header()
    
    # 确认信息
    print("\n请确认以下信息:")
    print(f"Token: ".ljust(15) + my_token[:10] + "..." + my_token[-5:])
    print(f"设备ID: ".ljust(15) + my_device_id)
    print(f"设备名称: ".ljust(15) + my_device_name)
    print(f"UUID: ".ljust(15) + my_uuid[:10] + "..." + my_uuid[-5:])
    
    confirm = input("\n信息是否正确? [y/n]: ")
    if confirm.lower() != 'y':
        print("已取消操作")
        return

    
    # 获取学期列表
    print("\n正在获取学期列表...")
    try:
        term_list_json = default_post("/run/listXnYearXqByStudentId", data='')
        term_list = json.loads(term_list_json)
        
        if term_list.get("code") != 200:
            print(f"获取学期列表失败: {term_list.get('msg', '未知错误')}")
            return
            
        terms = term_list.get("data", [])
        if not terms:
            print("没有找到任何学期数据")
            return
    except Exception as e:
        print(f"获取学期列表失败: {e}")
        return
    
    # 显示学期列表并让用户选择
    term_options = [f"{term['key']} ({term['sjd']})" for term in terms]
    term_idx = select_option(term_options, title="请选择学期")
    
    if term_idx is None:
        print("已取消操作")
        return
    
    selected_term = terms[term_idx]
    print(f"\n已选择: {selected_term['key']}")
    
    # 获取选定学期的跑步记录列表
    print("\n正在获取跑步记录...")
    try:
        run_list_json = default_post("/run/crsReocordInfoList", 
                                    data=json.dumps({"tableName": selected_term['value']}))
        run_list = json.loads(run_list_json)
        
        if run_list.get("code") != 200:
            print(f"获取跑步记录失败: {run_list.get('msg', '未知错误')}")
            return
        
        # 提取所有月份的跑步记录
        all_runs = []
        for month_data in run_list.get("data", {}).get("rank", []):
            all_runs.extend(month_data.get("rankList", []))
        
        if not all_runs:
            print(f"在{selected_term['key']}没有找到任何跑步记录")
            return
    except Exception as e:
        print(f"获取跑步记录失败: {e}")
        return
    
    run_options = [format_run_info(run) for run in all_runs]
    run_idx = select_option(run_options, title="请选择一条跑步记录")
    
    if run_idx is None:
        print("已取消操作")
        return
    
    selected_run = all_runs[run_idx]
    print(f"\n已选择: {run_options[run_idx]}")
    
    # 获取详细跑步记录
    print("\n正在获取详细记录...")
    key_ctx = {}
    try:
        run_detail_json = default_post("/run/crsReocordInfo", 
                                      data=json.dumps({
                                          "id": selected_run['id'], 
                                          "tableName": selected_term['value']
                                      }), key_ctx=key_ctx)
        
        # 解密记录
        key = b64decode(key_ctx["key"])
        text = gzip.decompress(decrypt_sm4(run_detail_json, key)).decode()
        run_detail = json.loads(text)
        
        if run_detail.get("code") != 200:
            print(f"获取详细记录失败: {run_detail.get('msg', '未知错误')}")
            return
    except Exception as e:
        print(f"获取或解析详细记录失败: {e}")
        return
    
    # 保存记录
    try:
        saved_path = save_history_record(text, args.history_path)
        print(f"\n记录已成功保存到: {saved_path}")
        
        # 显示记录摘要
        data = run_detail.get("data", {})
        print("\n记录摘要:")
        print(f"日期时间: {data.get('recordStartTime', '')} ~ {data.get('recordEndTime', '')}")
        print(f"跑步距离: {data.get('recordMileage', '0')}公里")
        print(f"配速: {data.get('recodePace', '0')}/公里")
        print(f"步频: {data.get('recodeCadence', '0')}")
        print(f"用时: {data.get('duration', '0')}秒")
        print(f"打卡点数: {data.get('recodeDislikes', '0')}")
        print(f"运动轨迹点: {len(data.get('pointsList', []))}个")
    except Exception as e:
        print(f"保存记录失败: {e}")
        return

if __name__ == "__main__":
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='云运动历史记录提取工具')
    parser.add_argument('--history_path', type=str, default='./tasks_else', 
                        help='历史记录保存路径')
    parser.add_argument("--conf_path", type=str, default="./config.ini",
                        help="配置文件路径")
    args = parser.parse_args()
    set_args(args.conf_path)
    from main import * # 重新加载配置，防止bug
    his(args) # main被占用了，所以用his代替