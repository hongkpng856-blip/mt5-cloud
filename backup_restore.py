# -*- coding: utf-8 -*-
"""
Tradotcom 完整 Backup/Restore 方案
=================================
目的：確保任何時候可以回覆到「而家呢個版本」— 所有嘢（code + 配置 + DB + MT5 狀態）一齊回覆 → 版本一致 → 唔會失效

Backup 包含：
  1. Git 版本（開發目錄 commit hash — 回覆用）
  2. 安裝目錄（$LOCALAPPDATA/TradotcomAgent — agent 全部 code + 配置）
  3. DB（instance/mt5cloud.db — user + agent + 配對庫）
  4. MT5 狀態（.chr + order.wnd + EA .mq5/.ex5 + 心跳 + trades 數據 + hotkeys.ini）
  5. 環境（agent 啟動參數 — agent_config.json fingerprint）

Restore 流程：
  1. Git checkout 到 backup 嘅 commit
  2. 安裝目錄還原（複製 backup 嘅 TradotcomAgent）
  3. DB 還原
  4. MT5 狀態還原（.chr/order.wnd/EA/心跳）
  5. 重啟 server + agent + watcher + alert_worker
"""
import os, sys, shutil, json, subprocess, time, datetime, zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ═══════════════ 路徑設定 ═══════════════
DEV_DIR     = r'C:\Users\hongk\Desktop\mt5-cloud'          # 開發目錄（git repo）
AGENT_DIR   = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')  # 安裝目錄
DB_PATH     = os.path.join(DEV_DIR, 'instance', 'mt5cloud.db')
MT5_DIR     = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
# MT5 terminal 目錄（自動偵測 — 有 MQL5 嗰個）
TERMINAL_DIR = None
if os.path.isdir(MT5_DIR):
    for _d in os.listdir(MT5_DIR):
        _cand = os.path.join(MT5_DIR, _d)
        if os.path.isdir(os.path.join(_cand, 'MQL5')):
            TERMINAL_DIR = _cand
            break

BACKUP_ROOT = r'C:\Users\hongk\Desktop\mt5-cloud\backups'   # backup 存放位置
os.makedirs(BACKUP_ROOT, exist_ok=True)


def make_backup(label=''):
    """建立完整 backup — 一個 zip 包含所有嘢"""
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    tag = f'{ts}_{label}' if label else ts
    # 1. Git commit hash
    git_hash = ''
    try:
        r = subprocess.run(['git', '-C', DEV_DIR, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=10)
        git_hash = r.stdout.strip()
    except Exception:
        pass

    backup_info = {
        'created': datetime.datetime.now().isoformat(),
        'git_commit': git_hash,
        'git_branch': '',
        'label': label,
        'files': {},
    }
    try:
        r = subprocess.run(['git', '-C', DEV_DIR, 'branch', '--show-current'], capture_output=True, text=True, timeout=10)
        backup_info['git_branch'] = r.stdout.strip()
    except Exception:
        pass

    # 2. 收集所有要 backup 嘅檔案
    collected = {}   # backup 內路徑 → 源路徑
    # 2a. 安裝目錄（agent code + 配置）— 唔要 log/lock/temp/setup
    if os.path.isdir(AGENT_DIR):
        for _f in os.listdir(AGENT_DIR):
            _fp = os.path.join(AGENT_DIR, _f)
            if os.path.isfile(_fp):
                _bn = os.path.basename(_f)
                if (_bn.endswith(('.log', '.pid', '.lock', '.running'))
                        or _bn.startswith(('.', '_'))
                        or 'Setup' in _bn):   # 排除 setup 檔（舊安裝器 — 唔需要）
                    continue
                collected[f'agent/{_f}'] = _fp
    # 2b. DB
    if os.path.isfile(DB_PATH):
        collected['db/mt5cloud.db'] = DB_PATH
    # 2c. MT5 狀態（.chr + order.wnd + EA + 心跳 + config）
    if TERMINAL_DIR:
        # 2c-1. Profiles/Charts（全部 profile — .chr + order.wnd）
        _charts_root = os.path.join(TERMINAL_DIR, 'MQL5', 'Profiles', 'Charts')
        if os.path.isdir(_charts_root):
            for _prof in os.listdir(_charts_root):
                _pd = os.path.join(_charts_root, _prof)
                if not os.path.isdir(_pd):
                    continue
                for _f in os.listdir(_pd):
                    if _f.endswith(('.chr', '.wnd')):
                        collected[f'mt5/charts/{_prof}/{_f}'] = os.path.join(_pd, _f)
        # 2c-2. EA（Experts — .mq5 + .ex5 + .set）
        _exp_root = os.path.join(TERMINAL_DIR, 'MQL5', 'Experts')
        if os.path.isdir(_exp_root):
            for _f in os.listdir(_exp_root):
                if _f.endswith(('.mq5', '.ex5', '.set')):
                    collected[f'mt5/experts/{_f}'] = os.path.join(_exp_root, _f)
        # 2c-2b. [ALERT] 2026-09-02 FIX（restore 測試發現：backup 唔齊 — 本機 Experts 得 5 隻 — metaeditor compile 刪咗其他）：
        # → EA 倉庫（static/ea_library — 一定有齊 10 隻 .mq5）補充（restore 時本機有齊）
        _lib_root = os.path.join(DEV_DIR, 'server', 'static', 'ea_library')
        if os.path.isdir(_lib_root):
            for _f in os.listdir(_lib_root):
                if _f.endswith(('.mq5', '.ex5')):
                    _arc = f'mt5/experts/{_f}'
                    if _arc not in collected:
                        collected[_arc] = os.path.join(_lib_root, _f)
        # 2c-2c. [ALERT] 2026-09-02 FIX v2（restore 測試發現）：EA 倉庫得 .mq5 冇 .ex5
        # → 本機冇 .ex5 時提示用 install-local 補（唔好喺度 compile — metaeditor compile 一個會刪其他 — 永遠唔齊）
        _exp_root2 = os.path.join(TERMINAL_DIR, 'MQL5', 'Experts')
        _lib_root2 = os.path.join(DEV_DIR, 'server', 'static', 'ea_library')
        if os.path.isdir(_lib_root2) and os.path.isdir(_exp_root2):
            _missing_ex5 = []
            for _f in os.listdir(_lib_root2):
                if not _f.endswith('.mq5'):
                    continue
                _base2 = os.path.splitext(_f)[0]
                if not os.path.isfile(os.path.join(_exp_root2, _base2 + '.ex5')):
                    _missing_ex5.append(_base2)
            if _missing_ex5:
                print(f'⚠️ [backup] 本機缺 {len(_missing_ex5)} 隻 .ex5: {_missing_ex5}')
                print(f'   → backup 會包含 .mq5（restore 時可 compile / 或者先喺網頁「加入配對庫」補齊）')
        # 2c-3. 心跳 + trades（Common/Files — state_ + trades_ + hb_）
        _cf = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        if os.path.isdir(_cf):
            for _f in os.listdir(_cf):
                if _f.startswith(('state_', 'trades_', 'hb_')):
                    collected[f'mt5/common/{_f}'] = os.path.join(_cf, _f)
        # 2c-4. config（hotkeys.ini）
        _cfg = os.path.join(TERMINAL_DIR, 'config', 'hotkeys.ini')
        if os.path.isfile(_cfg):
            collected['mt5/config/hotkeys.ini'] = _cfg
    # 2d. 開發目錄關鍵檔案（chr 模板 + skill 記錄）
    for _rel in ['agent/chr_template_base.chr.txt', 'agent/chr_template_README.md']:
        _fp = os.path.join(DEV_DIR, _rel)
        if os.path.isfile(_fp):
            collected[f'dev/{_rel}'] = _fp

    backup_info['files'] = {k: os.path.getsize(v) for k, v in collected.items()}

    # 3. 寫 zip
    zip_path = os.path.join(BACKUP_ROOT, f'backup_{tag}.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 先寫 info.json
        zf.writestr('info.json', json.dumps(backup_info, indent=2, ensure_ascii=False))
        for arc, src in collected.items():
            if os.path.isfile(src):
                zf.write(src, arc)

    print(f'✅ Backup 完成: {zip_path}')
    print(f'   Git commit: {git_hash} ({backup_info["git_branch"]})')
    print(f'   檔案數: {len(collected)}')
    print(f'   大小: {os.path.getsize(zip_path)/1024:.1f} KB')
    return zip_path


def list_backups():
    """列出所有 backup"""
    if not os.path.isdir(BACKUP_ROOT):
        print('冇 backup')
        return []
    backups = sorted([f for f in os.listdir(BACKUP_ROOT) if f.endswith('.zip')], reverse=True)
    for b in backups:
        p = os.path.join(BACKUP_ROOT, b)
        # 讀 info.json
        try:
            with zipfile.ZipFile(p) as zf:
                info = json.loads(zf.read('info.json'))
            print(f'  {b}  ({os.path.getsize(p)/1024:.0f} KB)  git={info.get("git_commit","?")[:8]}  label={info.get("label","")}')
        except Exception:
            print(f'  {b}  ({os.path.getsize(p)/1024:.0f} KB)')
    return backups


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Tradotcom 完整 Backup')
    parser.add_argument('--backup', action='store_true', help='建立 backup')
    parser.add_argument('--label', default='', help='backup 標籤（例如 pre-update-20260902）')
    parser.add_argument('--list', action='store_true', help='列出所有 backup')
    args = parser.parse_args()

    if args.list:
        list_backups()
    else:
        make_backup(args.label)
