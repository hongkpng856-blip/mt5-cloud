# 修 inject_control_layer.py — OnDeinit 加 reason Print
p = 'agent/inject_control_layer.py'
with open(p, encoding='utf-8') as f:
    t = f.read()

old = '''void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 '''
marker = '已停止'
new = '''void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 '''

# 搵 OnDeinit 模板（簡化 — 直接加 reason）
import re
# 搵「OnDeinit(const int reason)」後嘅 Print 行
pat = re.compile(r'(void OnDeinit\(const int reason\)\s*\{\s*if\(EnableLog\) Print\("🛑 [^"]+"\);)')
if pat.search(t):
    t2 = pat.sub(r'\1\n   if(EnableLog) Print("   [OnDeinit] reason=" + IntegerToString(reason));', t, count=1)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(t2)
    print('已修（OnDeinit reason Print）')
else:
    print('模板唔啱')
    # 顯示 OnDeinit 附近
    idx = t.find('OnDeinit')
    print(t[idx:idx+200] if idx >= 0 else '搵唔到 OnDeinit')
