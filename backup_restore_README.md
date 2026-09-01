# Tradotcom Backup / Restore 防禦方案

**目的**：確保任何時候可以回覆到「最後穩定版本」— 所有嘢（code + 配置 + DB + MT5 狀態）一齊回覆 → 版本一致 → **唔會失效**（你之前經歷：更新後回覆上一個版本 — 全部失效 — 因為淨係回覆 code 冇回覆配置/DB/MT5 狀態）。

## Backup（建立快照 — 更新前做）

```bash
# 完整 backup（包含：git commit + agent code + DB + MT5 狀態）
python backup_restore.py --backup --label "pre-update-xxx"
# 例如：更新前做
python backup_restore.py --backup --label "stable-20260902"

# 列出所有 backup
python backup_restore.py --list
```

Backup 存喺：`backups/backup_<日期>_<時間>_<label>.zip`

**包含咩**：
| 類別 | 內容 |
|---|---|
| git commit | 開發目錄版本（restore 時 checkout） |
| agent/ | 安裝目錄全部 code（agent.py/auto_attach.py/alert_worker.py 等）+ agent_config.json |
| db/ | mt5cloud.db（user + agent + 配對庫 + magic 表） |
| mt5/charts/ | .chr + order.wnd（MT5 圖表狀態 — 邊個 chart 掛邊隻 EA） |
| mt5/experts/ | EA .mq5 + .ex5（10 隻 testable EA） |
| mt5/common/ | 心跳 + trades 數據（state_<EA>.json + trades_<EA>.json） |
| mt5/config/ | hotkeys.ini（熱鍵設定） |

## Restore（回覆版本）

```bash
# 列出 backup → 揀一個
python restore_backup.py --list

# 完整 restore（自動：停服務 → git checkout → 還原 agent/DB/MT5 → 重啟 → 驗證）
python restore_backup.py --restore backup_20260902_031853_stable-20260902.zip
```

**Restore 流程**（自動）：
1. 停 server/agent/watcher/alert_worker（避免寫入衝突）
2. Git checkout 到 backup 嘅 commit（code 版本一致）
3. 還原安裝目錄（agent code + 配置）
4. 還原 DB（配對庫 + magic）
5. 還原 MT5 狀態（.chr/order.wnd/EA/心跳/hotkeys）
6. 重啟 server + agent + watcher + alert_worker
7. 驗證（server 200 + agent Registered + EA 心跳 FRESH）

## 最佳做法
- **更新前一定 backup**（label 標明 pre-update-<日期>）
- **重大里程碑 backup**（label 標明 stable-<日期> — 例如而家 `stable-20260902`）
- Restore 後驗證：網頁登入 → 配對庫見到 EA → 部署 → 心跳 FRESH → 完成

## 已建立嘅 backup
- `backups/backup_20260902_031853_stable-20260902.zip`（v0.11.06 — git `8e8deaa` — ⭐ 而家最後穩定版本）
