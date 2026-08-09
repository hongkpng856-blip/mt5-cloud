"""Down×N 位置穩定性測試 ×10：每次開圖表（Down×5=AUDUSD 位置）→ 部署 Support_Resist → log 睇實際 symbol"""
import os
import sys
import time
import subprocess
import glob

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal',
                       'D0E8209F77C8CF37AD8BF550E51FF075', 'MQL5', 'Logs')


def read_log():
    """讀最新 log 檔（UTF-16/8）"""
    logs = sorted(glob.glob(os.path.join(LOG_DIR, '*.log')), key=os.path.getmtime)
    for lf in logs[-1:]:
        with open(lf, 'rb') as f:
            raw = f.read()
        for enc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
            try:
                return raw.decode(enc)
            except Exception:
                continue
    return ''


def main():
    results = []
    for i in range(10):
        print(f'\n===== 測試 {i+1}/10：開圖表 Down×5 → 部署 Support_Resist =====')
        # 部署（auto_attach 開圖表 Down×5 + 熱鍵 + log）
        r = subprocess.run([sys.executable, '-u', 'agent/auto_attach.py',
                            '--ea', 'Support_Resist', '--symbol', 'AUDUSD',
                            '--tf', 'H1', '--magic', str(250000 + i), '--lot', '1'],
                           cwd=PROJECT, capture_output=True, timeout=90)
        out = r.stdout.decode('utf-8', errors='replace')
        print(f'  exit: {r.returncode}')
        # 讀 log — 搵最新 Support_Resist 啟動（symbol）
        time.sleep(3)
        text = read_log()
        sym = None
        for line in text.splitlines():
            if 'Support_Resist' in line and ('已启动' in line or '已啟動' in line):
                # 格式: ... Support_Resist (SYMBOL,H1) ... 已啟動
                idx = line.find('Support_Resist (')
                if idx >= 0:
                    rest = line[idx + len('Support_Resist ('):]
                    sym = rest.split(',')[0]
        results.append(sym)
        print(f'  ➡️ 實際圖表 symbol: {sym}')
        # 等 5 秒（下輪）
        time.sleep(5)
    # 總結
    print('\n========== 總結 ==========')
    print(f'10 次結果: {results}')
    target = 'AUDUSD'
    ok = sum(1 for s in results if s == target)
    print(f'目標 {target}: {ok}/10')
    if ok == 10:
        print('✅ Down×N 位置固定（10 次全部 AUDUSD）')
    else:
        wrong = [(i+1, s) for i, s in enumerate(results) if s != target]
        print(f'❌ Down×N 位置改變（{len(wrong)} 次唔同）: {wrong}')
    return 0 if ok == 10 else 1


if __name__ == '__main__':
    sys.exit(main())
