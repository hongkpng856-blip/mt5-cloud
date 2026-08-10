"""10 次穩定測試：添加 → 部署 → 剷除（用唔同 EA）"""
import os
import sys
import json
import time
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

EAS = ['Bollinger_Band', 'Breakout', 'Divergence', 'EMA_Cross', 'Grid_Trading',
       'Heikin_Ashi', 'Machine_Learn', 'Momentum', 'Price_Action', 'SMA_Cross']
CF = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal', 'Common', 'Files')
HOTKEYS_INI = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal',
                           'D0E8209F77C8CF37AD8BF550E51FF075', 'config', 'hotkeys.ini')


def heartbeat(ea):
    sf = os.path.join(CF, f'state_{ea}.json')
    if not os.path.isfile(sf):
        return None
    with open(sf, 'rb') as f:
        raw = f.read()
    try:
        d = json.loads(raw.decode('utf-8'))
    except Exception:
        d = json.loads(raw.decode('utf-16'))
    return d.get('status')


def hotkey_exists(ea):
    with open(HOTKEYS_INI, 'rb') as f:
        text = f.read().decode('utf-16')
    return ea in text


def deploy(ea, symbol='EURUSD', magic=240700):
    """部署（熱鍵）— 直接跑 auto_attach"""
    r = subprocess.run([sys.executable, '-u', 'agent/auto_attach.py',
                        '--ea', ea, '--symbol', symbol, '--tf', 'H1',
                        '--magic', str(magic), '--lot', '1'],
                       cwd=os.path.dirname(BASE), capture_output=True, timeout=90)
    out = r.stdout.decode('utf-8', errors='replace')
    ok = '附加成功' in out or '成功 attach' in out or '附加流程完成' in out
    return ok, out[-200:]


def main():
    results = []
    # 確保熱鍵全部存在（部署前）
    missing = [ea for ea in EAS if not hotkey_exists(ea)]
    print(f'缺熱鍵: {missing}')
    for i, ea in enumerate(EAS, 1):
        print(f'\n===== 測試 {i}/10: {ea} =====')
        row = {'ea': ea, 'deploy': False, 'heartbeat': False, 'delete': False, 're_add': False}
        # 1. 部署
        ok, tail = deploy(ea, magic=240700 + i)
        row['deploy'] = ok
        print(f'  部署: {"✅" if ok else "❌"}')
        if not ok:
            print(f'  tail: {tail}')
        # 2. 心跳
        time.sleep(8)
        hb = heartbeat(ea)
        row['heartbeat'] = hb == 'running'
        print(f'  心跳: {"✅ running" if row["heartbeat"] else f"❌ {hb}"}')
        results.append(row)
    # 總結
    print('\n===== 總結 =====')
    ok_count = sum(1 for r in results if r['deploy'] and r['heartbeat'])
    print(f'部署+心跳成功: {ok_count}/10')
    for r in results:
        print(f"  {r['ea']}: 部署{'✅' if r['deploy'] else '❌'} 心跳{'✅' if r['heartbeat'] else '❌'}")
    return 0 if ok_count == 10 else 1


if __name__ == '__main__':
    sys.exit(main())
