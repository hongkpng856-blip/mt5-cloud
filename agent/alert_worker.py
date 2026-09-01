# ============================================================
# alert_worker.py — 警告視窗（重製版 v2 — 2026-08-11）
# 獨立 process（讀 .ai_control.show / .ai_control.steps flag）
# 設計原則：
#   1. 穩定 — 固定大小、唔自動關、唔抽搐、唔殘留
#   2. 清晰 — 標題「遠端控制」+ 操作名 + 步驟（累積）
#   3. 成功/失敗一目了然（綠/紅 + 文字）
#   4. 按鈕二選一：操作期間緊急停止 / 完成後確定（撳先關）
# ============================================================
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys
import json
import time
import socket
import tkinter as tk

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHOW_FLAG = os.path.join(AGENT_DIR, '.ai_control.show')
STEPS_FLAG = os.path.join(AGENT_DIR, '.ai_control.steps')

# [ALERT] 2026-08-12：單實例守衛（防雙視窗 — 用戶投訴「兩個相同嘅嘢」）
# 用 bind port 5004（同 detector 5003 模式一致 — process 死咗 port 自動釋放）
_SINGLE_PORT = 5004
try:
    _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _sock.bind(('127.0.0.1', _SINGLE_PORT))
    _sock.listen(1)
except OSError:
    print(f'[WARN] :{_SINGLE_PORT} alert_worker already running, this instance exits (single-instance guard)')
    sys.exit(0)

# 窗口狀態
shown = False
_all_done_shown = False
_last_sig = None


def build_window(root):
    """建立警告視窗（右下角固定位置 — 唔遮 MT5 操作區）
    2026-08-12 UI 專業化：統一間距（16px 網格）+ 自訂警告 icon（唔用 default tkinter）"""
    # [FP] 2026-08-31 指紋：讀 agent_config.json 攞 account — title 顯示「邊個 account 嘅 AI 控制」
    _fp_acc = ''
    try:
        _cfg_fp = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent', 'agent_config.json')
        if os.path.isfile(_cfg_fp):
            import json as _j_fp
            _cfg_fp_d = _j_fp.load(open(_cfg_fp, encoding='utf-8'))
            _fp_acc = _cfg_fp_d.get('account', '') or _cfg_fp_d.get('fingerprint', '')
    except Exception:
        pass
    root.title(f'AI 遠端控制{(" - " + _fp_acc) if _fp_acc else ""}')
    root.attributes('-topmost', True)
    # 固定大小（專業 UI — 步驟區夠空間；2026-08-12：410 — 用戶「唔好留咁多空白」）
    W, H = 380, 410
    try:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f'{W}x{H}+{sw - W - 24}+{sh - H - 96}')
    except Exception:
        root.geometry(f'{W}x{H}+1200+560')
    root.resizable(False, False)
    # [ALERT] 2026-08-11：鎖死最小+最大（內容驅動自動 resize 根治 — 用戶話視窗大細抖動仲有）
    root.minsize(W, H)
    root.maxsize(W, H)
    root.overrideredirect(False)

    # 背景
    root.configure(bg='#1e1e2e')

    # 自訂 icon（[WARN] 2026-08-12 專業化：綠色圓形 + 白色「!」警告符號 — 唔用 default tkinter 羽毛 / 像素圖案）
    try:
        from PIL import Image, ImageDraw, ImageTk
        _img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        _d = ImageDraw.Draw(_img)
        _d.ellipse((4, 4, 60, 60), fill='#34d399')
        _d.polygon([(32, 14), (50, 46), (14, 46)], fill='#1e1e2e')
        _d.rectangle((29, 26, 35, 38), fill='#34d399')
        _d.rectangle((29, 42, 35, 46), fill='#34d399')
        root.iconphoto(True, ImageTk.PhotoImage(_img))
        root._icon_ref = _img  # 保持 reference（防 GC）
    except Exception:
        # fallback：無 PIL — 用 tk 畫簡潔 icon
        try:
            img = tk.PhotoImage(width=32, height=32)
            for y in range(32):
                for x in range(32):
                    img.put('#34d399' if (x + y) % 3 != 0 else '#1e1e2e', (x, y))
            root.iconphoto(True, img)
        except Exception:
            pass

    # 頂部色條（強調色）
    bar = tk.Frame(root, bg='#34d399', height=4)
    bar.pack(fill='x')

    # 標題行（統一間距 16px）
    head = tk.Frame(root, bg='#1e1e2e')
    head.pack(fill='x', padx=16, pady=(12, 4))
    tk.Label(head, text='⛨', font=('Segoe UI Symbol', 18), fg='#34d399', bg='#1e1e2e').pack(side='left')
    tk.Label(head, text='遠端控制', font=('Microsoft JhengHei', 15, 'bold'), fg='#e2e8f0', bg='#1e1e2e').pack(side='left', padx=8)

    # 狀態 label（統一間距）
    root._status_label = tk.Label(root, text='執行中…', font=('Microsoft JhengHei', 13, 'bold'), fg='#fbbf24', bg='#1e1e2e', anchor='w')
    root._status_label.pack(fill='x', padx=16, pady=(4, 4))

    # 分隔線
    tk.Frame(root, bg='#2d2d44', height=1).pack(fill='x', padx=12, pady=6)

    # 步驟列表（統一間距 16px）
    root._steps_frame = tk.Frame(root, bg='#1e1e2e')
    root._steps_frame.pack(fill='both', expand=True, padx=16, pady=6)

    # 按鈕區（固定底部 — 唔亂跳）
    root._btn_frame = tk.Frame(root, bg='#1e1e2e')
    root._btn_frame.pack(fill='x', padx=16, pady=(4, 14))

    # 緊急停止（操作期間顯示）
    root._stop_btn = tk.Button(root._btn_frame, text='緊急停止', font=('Microsoft JhengHei', 12, 'bold'),
                               fg='#fff', bg='#ef4444', activebackground='#dc2626', activeforeground='#fff',
                               relief='flat', bd=0, cursor='hand2', width=10, pady=8)
    root._stop_btn.configure(command=lambda: emergency_stop(root))
    # 確定（完成後顯示 — 撳先關）
    root._done_btn = tk.Button(root._btn_frame, text='確定', font=('Microsoft JhengHei', 12, 'bold'),
                               fg='#fff', bg='#34d399', activebackground='#10b981', activeforeground='#fff',
                               relief='flat', bd=0, cursor='hand2', width=10, pady=6)
    # [ALERT] 2026-08-12 FIX：確定撳咗 → withdraw + reset shown（否則下次 flag 寫 → if not shown False → 唔 deiconify → 視窗永遠隱藏 →「冇出現警告視窗」）
    # [ALERT] 2026-08-13 FIX：確定 → 刪 SHOW_FLAG（.ai_control.show — 唔刪 → 下一 round poll has_flag=True → 又彈出嚟！「確定完又彈」根源）
    def _done_close():
        global shown
        root.withdraw()
        shown = False
        try:
            if os.path.isfile(SHOW_FLAG):
                os.remove(SHOW_FLAG)
        except Exception:
            pass
    root._done_btn.configure(command=_done_close)

    # 初始隱藏（等 flag）
    root.withdraw()
    return root


def emergency_stop(root):
    """緊急停止 — 寫 flag（watcher/auto_attach 會 check）+ 隱藏視窗"""
    global shown
    try:
        with open(os.path.join(AGENT_DIR, '.ai_control.abort'), 'w', encoding='utf-8') as f:
            f.write('1')
        print('[alert_worker] EMERGENCY STOP triggered', flush=True)
    except Exception:
        pass
    root.withdraw()
    shown = False  # [ALERT] 2026-08-12 FIX：reset shown（下次 flag 可以再顯示）
    # [ALERT] 2026-08-13 FIX：緊急停止都刪 SHOW_FLAG（唔刪 → 下一 round poll has_flag=True → 又彈出嚟）
    try:
        if os.path.isfile(SHOW_FLAG):
            os.remove(SHOW_FLAG)
    except Exception:
        pass


def read_steps():
    """讀 steps（失敗返回 []）"""
    try:
        if os.path.isfile(STEPS_FLAG):
            with open(STEPS_FLAG, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


_last_render_key = None


def render_steps(root, data):
    """渲染步驟（累積 — 唔消失）
    [ALERT] 2026-08-11 修：① 內容一樣 → skip ② 增量更新 ③ 預留固定行數（步驟加/減 — 空行填補 — 內容位置唔跳 — 用戶投訴抖動）"""
    global _last_render_key
    key = json.dumps(data, ensure_ascii=False)
    if key == _last_render_key:
        return
    _last_render_key = key
    children = root._steps_frame.winfo_children()
    MAX_ROWS = 6  # 預留最大行數（內容位置固定 — 唔跳）
    for i in range(MAX_ROWS):
        if i < len(data):
            s = data[i]
            text = s.get('text', '')
            st = s.get('status', 'pending')
            if st == 'doing':
                mark, color = '[進行中]', '#fbbf24'
            elif st == 'done':
                mark, color = '[完成]', '#34d399'
            else:
                mark, color = '[等待]', '#71717a'
            if '失敗' in text:
                mark, color = '[失敗]', '#f87171'
            full = f'{mark} {text}'
        else:
            # 空行填補（位置固定 — 步驟加/減唔會跳）
            full = ''
            color = '#1e1e2e'
        if i < len(children):
            children[i].config(text=full, fg=color)
        else:
            lbl = tk.Label(root._steps_frame, text=full, font=('Microsoft JhengHei', 11), fg=color,
                           bg='#1e1e2e', anchor='w', wraplength=300, justify='left')
            lbl.pack(fill='x', pady=1)
    # 多餘 destroy
    for w in children[MAX_ROWS:]:
        w.destroy()


def main():
    global shown, _all_done_shown, _last_sig
    root = tk.Tk()
    build_window(root)

    while True:
        try:
            root.update_idletasks()
            root.update()
            # [ALERT] 2026-08-11 修：只喺「偏離」先修正（唔係每 round set — 之前每 round set 觸發 re-layout 抖動；唔 set 又會內容少時縮細）
            # 2026-08-12 UI 專業化：新尺寸 380×410
            try:
                _w = root.winfo_width()
                _h = root.winfo_height()
                if _h < 410 or _w < 380:
                    root.geometry(f'380x410+{root.winfo_screenwidth() - 380 - 24}+{root.winfo_screenheight() - 410 - 96}')
            except Exception:
                pass
            time.sleep(0.4)

            has_flag = os.path.isfile(SHOW_FLAG)
            # 讀 flag 內容（操作名 — 用嚟偵測新任務）
            sig = None
            if has_flag:
                try:
                    with open(SHOW_FLAG, 'r', encoding='utf-8') as f:
                        sig = f.read().strip() or '操作中'
                except Exception:
                    sig = '操作中'

            steps = read_steps()
            has_doing = any(s.get('status') == 'doing' for s in steps)
            all_done = bool(steps) and all(s.get('status') == 'done' for s in steps)
            has_fail = any('失敗' in (s.get('text', '') if isinstance(s, dict) else '') for s in steps)

            if has_flag:
                # [ALERT] 新任務偵測（flag 內容變咗 / 有 doing 步驟）→ 重置按鈕狀態
                if sig != _last_sig or has_doing:
                    _last_sig = sig
                    _all_done_shown = False
                    # 操作期間：確定隱藏 + 緊急停止顯示 + 狀態「處理中」
                    # [ALERT] 2026-09-01 FIX（user實測：警告視窗卡住冇關 — TclError crash）：root 可能已銷毀（WM_CLOSE）→ 檢查先 call
                    try:
                        if root.winfo_exists():
                            root._done_btn.pack_forget()
                            root._stop_btn.pack(fill='x')
                            root._status_label.config(text=f'執行中：{sig}', fg='#fbbf24')
                    except tk.TclError:
                        raise
                if not shown:
                    root.deiconify()
                    shown = True
                render_steps(root, steps)
                if all_done:
                    # 完成：確定顯示（撳先關）+ 緊急停止隱藏 + 狀態 綠/紅
                    if not _all_done_shown:
                        _all_done_shown = True
                        root._stop_btn.pack_forget()
                        root._done_btn.pack(fill='x')
                        if has_fail:
                            root._status_label.config(text=f'失敗（{sig}）', fg='#f87171')
                        else:
                            root._status_label.config(text='已完成', fg='#34d399')
            else:
                # flag 冇 — 視窗唔自動關（用戶撳確定先關）— [ALERT] 2026-08-12 FIX：都要 render（steps 完成後顯示「已完成」+ 確定 — 唔停留舊內容）
                if shown:
                    render_steps(root, steps)
                    if all_done and not _all_done_shown:
                        _all_done_shown = True
                        root._stop_btn.pack_forget()
                        root._done_btn.pack(fill='x')
                        if has_fail:
                            root._status_label.config(text='已完成（有失敗步驟）', fg='#f87171')
                        else:
                            root._status_label.config(text='已完成', fg='#34d399')
        except tk.TclError:
            # [ALERT] 2026-08-29 FIX：TclError 唔好 break（之前 break → process 死 → 警告視窗永遠冇 → 用戶投訴「警告視窗冇彈」）
            # WM_CLOSE / 視窗被銷毀 → root.update() 拋 TclError → 之前 break 成個 loop → alert_worker 死
            # 修復：記錄 + 重建視窗（保持 process 生存 — 下次 flag 再彈）
            try:
                import traceback as _tb3
                with open(os.path.join(AGENT_DIR, 'alert_worker.log'), 'a', encoding='utf-8') as _f:
                    _f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] TclError — 重建視窗\n{_tb3.format_exc()}\n")
            except Exception:
                pass
            try:
                root.destroy()
            except Exception:
                pass
            try:
                root = tk.Tk()
                build_window(root)
                shown = False
                _all_done_shown = False
                _last_sig = None
                time.sleep(1.0)
                continue
            except Exception as _e2:
                try:
                    with open(os.path.join(AGENT_DIR, 'alert_worker.log'), 'a', encoding='utf-8') as _f:
                        _f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 重建失敗: {_e2}\n")
                except Exception:
                    pass
                time.sleep(2.0)
                continue
        except Exception as _e:
            # [ALERT] 2026-08-12 FIX：唔好食晒 exception — 記錄（診斷「可視化步驟停咗」）
            try:
                import traceback as _tb2
                print(f'[alert_worker] loop error: {_e}', flush=True)
                with open(os.path.join(AGENT_DIR, 'alert_worker.log'), 'a', encoding='utf-8') as _f:
                    _f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {_e}\n{_tb2.format_exc()}\n")
            except Exception:
                pass
            time.sleep(0.5)
            continue


if __name__ == '__main__':
    # [ALERT] crash log（死因記錄）
    try:
        main()
    except Exception as _e:
        try:
            import traceback as _tb
            with open(os.path.join(AGENT_DIR, 'alert_worker.log'), 'a', encoding='utf-8') as _f:
                _f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {_e}\n{_tb.format_exc()}\n")
        except Exception:
            pass
