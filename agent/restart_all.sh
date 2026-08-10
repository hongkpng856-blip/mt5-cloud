#!/bin/bash
# ============================================================
# MT5 Cloud — 一鍵重啟所有服務（單實例模式）
# 用法：bash agent/restart_all.sh
# 效果：殺晒所有 python → 起 1 個 server :5001 + 1 個 detector :5003
# ============================================================
set -e
cd "$(dirname "$0")/.."

echo "========================================"
echo "  MT5 Cloud Restart All (單實例模式)"
echo "========================================"

# 1. Kill 所有 python（server + detector + 舊 duplicates）
echo "[1/4] Killing all python processes..."
taskkill -f -im python.exe 2>/dev/null || true
sleep 3

# 確認 port 釋放
echo "[2/4] Checking ports..."
if netstat -ano | grep -q ":5001.*LISTENING"; then
    echo "  ⚠️  :5001 still occupied, killing again..."
    for pid in $(netstat -ano | grep ":5001.*LISTENING" | awk '{print $NF}' | sort -u); do
        taskkill -f -pid "$pid" 2>/dev/null || true
    done
    sleep 2
fi
if netstat -ano | grep -q ":5003.*LISTENING"; then
    for pid in $(netstat -ano | grep ":5003.*LISTENING" | awk '{print $NF}' | sort -u); do
        taskkill -f -pid "$pid" 2>/dev/null || true
    done
    sleep 2
fi
echo "  ✅ Ports clear"

# 3. Start server (background)
echo "[3/4] Starting server :5001..."
export PORT=5001
nohup python -u server/app.py > /tmp/mt5cloud_server.log 2>&1 &
echo "  ✅ Server PID $!"

# 4. Start detector
echo "[4/4] Starting detector :5003..."
nohup python -u agent/auto_trade_detector.py > /tmp/mt5cloud_detector.log 2>&1 &

# 🚨 2026-08-10 修：殺晒所有 python 之後 — 要起返 watcher + alert_worker（唔係會死 — 配對/部署冇人處理！）
echo "[4.5] Starting watcher + alert_worker..."
sleep 2
nohup python -u agent/deploy_watcher.py > /tmp/mt5cloud_watcher.log 2>&1 &
nohup python -u agent/alert_worker.py > /tmp/mt5cloud_alert.log 2>&1 &

echo "✅ 完成！Server: http://localhost:5001"
# 5. Health check
echo ""
echo "========================================"
echo "  健康檢查"
echo "========================================"
sleep 5
curl -s --max-time 3 http://localhost:5001/health && echo " <- Server OK"
curl -s --max-time 3 http://localhost:5003/health && echo " <- Detector OK"
echo ""
echo "✅ 完成！Server: http://localhost:5001"
