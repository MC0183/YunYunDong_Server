#!/bin/bash
# ==========================================
# 云运动动态多任务调度脚本 (v2)
# 依赖: task_manager.py 生成的 tasks.json
# ==========================================

LOG_DIR="/tasks/log"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
MAIN_LOG="${LOG_DIR}/main_cron.log"
TASKS_JSON="/tasks/tasks.json"

exec >> "$MAIN_LOG" 2>&1

# ====== 主动从 NTP 服务器同步时间（防重启后时间未同步导致调度异常）======
# BusyBox ntpd: -n 前台模式, -q 同步后退出, -p 指定 NTP 服务器
NTP_SERVERS="ntp.aliyun.com 0.openwrt.pool.ntp.org cn.pool.ntp.org"
SYNC_OK=false
for server in $NTP_SERVERS; do
    echo "[NTP-SYNC] 正在从 ${server} 同步时间..."
    ntpd -n -q -p "$server" 2>/dev/null
    if [ $? -eq 0 ] && [ "$(date +%Y)" -ge 2026 ]; then
        echo "[NTP-SYNC] 时间同步成功: $(date +'%Y-%m-%d %H:%M:%S')"
        SYNC_OK=true
        break
    fi
done
if [ "$SYNC_OK" = false ]; then
    echo "[NTP-WARN] 所有 NTP 服务器同步失败，使用当前系统时间继续（当前年份: $(date +%Y)）"
fi
# ============================================================

echo "=================================================="
echo "[[ 任务批次启动: $(date +'%Y-%m-%d %H:%M:%S') ]]"
echo "正在加载 tasks.json 配置..."
echo "=================================================="

if [ ! -f "$TASKS_JSON" ]; then
    echo "[ERROR] 未找到 $TASKS_JSON，请先运行 task_manager.py 添加任务。"
    exit 1
fi

# 安全解析 JSON 输出: ID|START_TIME|DIR_PATH
TASK_LIST=$(python3 -c "
import json, sys
try:
    with open('$TASKS_JSON', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for t in data.get('tasks', []):
        enabled = str(t.get('enabled', True))
        print(f\"{t['id']}|{t['start_time']}|{t['dir_path']}|{enabled}\")
except Exception as e:
    print(f'[JSON Parse Error] {e}', file=sys.stderr)
    sys.exit(1)
")

if [ -z "$TASK_LIST" ]; then
    echo "[WARNING] tasks.json 中无有效任务，退出。"
    exit 0
fi

while IFS='|' read -r PROJ START_TIME DIR_PATH ENABLED; do
    if [ "$ENABLED" != "True" ]; then
        echo "[SKIP] 任务 ${PROJ} 已禁用，跳过执行。"
        continue
    fi
(
    # 计算距离目标时间的延迟（秒）
    CURRENT_MIN=$(date +'%H:%M' | awk -F: '{print $1*60 + $2}')
    TARGET_MIN=$(echo "$START_TIME" | awk -F: '{print $1*60 + $2}')
    # 目标时间未到则等待，已过则立即执行
    if [ $TARGET_MIN -gt $CURRENT_MIN ]; then
        DELAY=$(( (TARGET_MIN - CURRENT_MIN) * 60 ))
    else
        DELAY=0
    fi

    LOG_FILE="${LOG_DIR}/${PROJ}_${TIMESTAMP}.log"

    # 1. 写入任务开始时间
    {
        echo "=================================================="
        echo "[START] 任务 ${PROJ} 启动时间: $(date +'%Y-%m-%d %H:%M:%S') (目标: ${START_TIME}, 调度延迟: ${DELAY}s)"
        echo "=================================================="
        echo "[PROCESS] >>> 任务运行日志开始 <<<"
        echo "=================================================="
    } > "$LOG_FILE"

    if [ ! -d "$DIR_PATH" ]; then
        echo "[ERROR] 目录 ${DIR_PATH} 不存在！" >> "$LOG_FILE"
        echo "[WARNING] ${PROJ} 启动失败：目录未找到" >> "$MAIN_LOG"
        { echo "[RESULT] 任务 ${PROJ} 异常终止 (目录缺失) at $(date +'%Y-%m-%d %H:%M:%S')"; } >> "$LOG_FILE"
        exit 1
    fi

    cd "$DIR_PATH" || {
        echo "[ERROR] 无法切换到 ${DIR_PATH} 目录！" >> "$LOG_FILE"
        exit 1
    }

    # 对齐目标时间
    if [ $DELAY -gt 0 ]; then
        echo "[调度] 等待 ${DELAY} 秒以对齐目标时间 ${START_TIME}..." >> "$LOG_FILE"
        sleep $DELAY
    fi

    # 2. 运行主程序并记录过程
    /usr/bin/python3 "$DIR_PATH/main.py" -a -d -t "$DIR_PATH/tasks_fch" >> "$LOG_FILE" 2>&1
    STATUS=$?

    # 3. 写入任务运行结果
    CURRENT_TIME=$(date +'%Y-%m-%d %H:%M:%S')
    {
        echo "=================================================="
        echo "[PROCESS] >>> 任务运行日志结束 <<<"
        echo "=================================================="
        case $STATUS in
            0) echo "[SUCCESS] 任务 ${PROJ} 成功完成！ (退出码: 0) at ${CURRENT_TIME}" ;;
            1) echo "[FAILED] 任务 ${PROJ} 失败：Token过期或无法访问系统资源 (退出码: 1) at ${CURRENT_TIME}" ;;
            2) echo "[FAILED] 任务 ${PROJ} 失败：服务端判定成绩不合格 (退出码: 2) at ${CURRENT_TIME}" ;;
            3) echo "[FAILED] 任务 ${PROJ} 失败：发生其他未知代码错误 (退出码: 3) at ${CURRENT_TIME}" ;;
            *) echo "[FAILED] 任务 ${PROJ} 失败：未预期的系统错误 (退出码: ${STATUS}) at ${CURRENT_TIME}" ;;
        esac
        echo "=================================================="
    } >> "$LOG_FILE"

    case $STATUS in
        0) echo "[SUCCESS] ${PROJ} 执行成功" ;;
        *) echo "[WARNING] ${PROJ} 执行异常 (Code: $STATUS)" ;;
    esac

    # 4. 更新运行统计到 tasks.json（含文件锁防并发）
    UPDATE_OUTPUT=$(python3 -c '
import json, sys, os, fcntl

task_id = sys.argv[1]
status = int(sys.argv[2])
current_time = sys.argv[3]
tasks_json = sys.argv[4]
msgs = []

try:
    lock_file = tasks_json + ".lock"
    open(lock_file, "a").close()

    with open(lock_file, "r+") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            with open(tasks_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            for t in data.get("tasks", []):
                if t["id"] == task_id:
                    stats = t.setdefault("run_stats", {"total": 0, "success": 0, "fail": 0, "last_run": "", "last_status": ""})
                    stats["total"] = stats.get("total", 0) + 1
                    if status == 0:
                        stats["success"] = stats.get("success", 0) + 1
                    else:
                        stats["fail"] = stats.get("fail", 0) + 1
                    stats["last_run"] = current_time
                    stats["last_status"] = str(status)

                    max_runs = t.get("max_runs")
                    if max_runs is not None and stats["total"] >= max_runs:
                        t["enabled"] = False
                        msgs.append("[AUTO-DISABLE] 任务 {} 已达到最大运行次数 ({})，已自动禁用".format(task_id, max_runs))
                    break
            with open(tasks_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
except Exception as e:
    msgs.append("[ERROR] 更新运行统计失败: {}".format(e))

for m in msgs:
    print(m)
' "$PROJ" "$STATUS" "$CURRENT_TIME" "$TASKS_JSON")
    if [ -n "$UPDATE_OUTPUT" ]; then
        echo "$UPDATE_OUTPUT" >> "$LOG_FILE"
        echo "$UPDATE_OUTPUT"
    fi

    # 5. 从服务器拉取真实跑步数据（更新 server_total，纯 shell 超时控制）
    FETCH_OUTFILE=$(mktemp /tmp/fetch_stats_XXXXXX 2>/dev/null || echo "/tmp/fetch_stats_$$.tmp")
    python3 "$(dirname "$TASKS_JSON")/fetch_server_stats.py" "$DIR_PATH/config.ini" > "$FETCH_OUTFILE" 2>/dev/null &
    FETCH_PID=$!
    # 后台启动一个 15 秒超时看门狗，到期 kill 掉进程
    (sleep 15 && kill $FETCH_PID 2>/dev/null) &
    WATCHDOG_PID=$!
    wait $FETCH_PID 2>/dev/null
    FETCH_STATUS=$?
    # 取消看门狗（如果还没触发）
    kill $WATCHDOG_PID 2>/dev/null
    FETCH_RESULT=$(cat "$FETCH_OUTFILE" 2>/dev/null)
    rm -f "$FETCH_OUTFILE"
    if [ $FETCH_STATUS -eq 0 ] && [ -n "$FETCH_RESULT" ]; then
        FETCH_TOTAL=$(echo "$FETCH_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_runs', '-'))" 2>/dev/null)
        FETCH_KM=$(echo "$FETCH_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_km', '-'))" 2>/dev/null)
        if [ -n "$FETCH_TOTAL" ] && [ "$FETCH_TOTAL" != "-" ]; then
            echo "[SERVER-STATS] ${PROJ} 服务器记录: ${FETCH_TOTAL} 次, ${FETCH_KM} 公里" >> "$LOG_FILE"
            # 回写到 tasks.json
            python3 -c '
import json, sys, os, fcntl
task_id, total, km, tasks_json = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
lock_file = tasks_json + ".lock"
open(lock_file, "a").close()
with open(lock_file, "r+") as lock_f:
    fcntl.flock(lock_f, fcntl.LOCK_EX)
    try:
        with open(tasks_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        for t in data.get("tasks", []):
            if t["id"] == task_id:
                stats = t.setdefault("run_stats", {})
                stats["server_total"] = total
                stats["server_total_km"] = km
                stats["server_fetch_time"] = "'$(date +'%Y-%m-%d %H:%M:%S')'"
                break
        with open(tasks_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    finally:
        fcntl.flock(lock_f, fcntl.LOCK_UN)
' "$PROJ" "$FETCH_TOTAL" "$FETCH_KM" "$TASKS_JSON" 2>/dev/null || true
        fi
    fi

) &
done <<< "$TASK_LIST"

wait
echo "=================================================="
echo "[[ 任务批次结束: $(date +'%Y-%m-%d %H:%M:%S') ]]"
echo "=================================================="
