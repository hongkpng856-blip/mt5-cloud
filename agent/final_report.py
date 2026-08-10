"""
Auto-attach execution report.
Writes final status to log file.
"""
import os, time, glob

APPDATA = os.environ.get('APPDATA', '')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
EXPERT_DIR = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                         'D0E8209F77C8CF37AD8BF550E51FF075', 'MQL5', 'Experts')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}

all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                   if os.path.basename(f) not in SYSTEM_EAS])

# Check heartbeats
running = []
not_running = []
for ea in ea_names:
    hb = os.path.join(COMMON_FILES, f'hb_{ea}.txt')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        if age < 60:
            running.append((ea, age))
        else:
            not_running.append((ea, f"stale ({age:.0f}s)"))
    else:
        not_running.append((ea, "no heartbeat"))

# Log final state
with open(LOG_FILE, 'a', encoding='utf-8') as f:
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    f.write(f"\n[{ts}] ============================================================\n")
    f.write(f"[{ts}] AUTO-ATTACH JOB COMPLETE\n")
    f.write(f"[{ts}] ============================================================\n")
    f.write(f"[{ts}] Total EAs: {len(ea_names)}\n")
    f.write(f"[{ts}] Running: {len(running)}\n")
    f.write(f"[{ts}] Not running: {len(not_running)}\n")
    for ea, reason in running:
        f.write(f"[{ts}]   ✅ {ea}: heartbeat {reason:.0f}s\n")
    for ea, reason in not_running:
        f.write(f"[{ts}]   ❌ {ea}: {reason}\n")
    f.write(f"[{ts}] \n")
    f.write(f"[{ts}] ATTEMPTED METHODS:\n")
    f.write(f"[{ts}]   1. auto_attach_all.py (pyautogui double-click in Navigator) → FAILED\n")
    f.write(f"[{ts}]   2. deploy_cron.py (PostMessage keyboard + pyautogui right-click) → FAILED\n")
    f.write(f"[{ts}]   3. deploy_v5.py (right-click context menu) → FAILED\n")
    f.write(f"[{ts}]   4. deploy_agenthelper.py (PostMessage keyboard shortcuts) → FAILED\n")
    f.write(f"[{ts}]   5. ShellExecute .tpl + dialog interaction → PARTIAL (dialog appeared once)\n")
    f.write(f"[{ts}]   6. MetaEditor compilation → FAILED (CMD args not supported)\n")
    f.write(f"[{ts}]   7. deploy_rightclick.py (right-click context menu + WM_CHAR) → FAILED\n")
    f.write(f"[{ts}] \n")
    f.write(f"[{ts}] ROOT CAUSE: MT5 GUI automation from background cron process is unreliable.\n")
    f.write(f"[{ts}]   - pyautogui mouse clicks work, keyboard send_keys doesn't\n")
    f.write(f"[{ts}]   - PostMessage keyboard works for dialogs but not main menu\n")
    f.write(f"[{ts}]   - WM_COMMAND toggle commands don't work from background\n")
    f.write(f"[{ts}]   - The Navigator double-click doesn't trigger EA Properties dialog\n")
    f.write(f"[{ts}]   - .tpl file association may not be set for MT5\n")
    f.write(f"[{ts}] \n")
    f.write(f"[{ts}] RECOMMENDATION: Deploy manually from MT5 GUI, or run auto_attach.py\n")
    f.write(f"[{ts}]   from a user-interactive process (not cron/background).\n")
    f.write(f"[{ts}] ============================================================\n")

print(f"Report written to {LOG_FILE}")
print(f"\nFinal State:")
print(f"  Total EAs: {len(ea_names)}")
print(f"  Running: {len(running)}")
print(f"  Not running: {len(not_running)}")
for ea, reason in running:
    print(f"    ✅ {ea}: heartbeat {reason:.0f}s")
for ea, reason in not_running:
    print(f"    ❌ {ea}: {reason}")
