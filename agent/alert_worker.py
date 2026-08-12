# ============================================================
# alert_worker.py — 警告視窗（重製版 v2 — 2026-08-11）
# 獨立 process（讀 .ai_control.show / .ai_control.steps flag）
# 設計原則：
#   1. 穩定 — 固定大小、唔自動關、唔抽搐、唔殘留
#   2. 清晰 — 標題「遙距控制」+ 操作名 + 步驟（累積）
#   3. 成功/失敗一目了然（綠/紅 + 文字）
#   4. 按鈕二選一：操作期間緊急停止 / 完成後確定（撳先關）
# ============================================================
import os
import sys
import json
import time
import socket
import tkinter as tk

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHOW_FLAG = os.path.join(AGENT_DIR, '.ai_control.show')
STEPS_FLAG = os.path.join(AGENT_DIR, '.ai_control.steps')

# 🚨 2026-08-12：單實例守衛（防雙視窗 — 用戶投訴「兩個相同嘅嘢」）
# 用 bind port 5004（同 detector 5003 模式一致 — process 死咗 port 自動釋放）
_SINGLE_PORT = 5004
try:
    _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _sock.bind(('127.0.0.1', _SINGLE_PORT))
    _sock.listen(1)
except OSError:
    print(f'⚠️ :{_SINGLE_PORT} 已有 alert_worker 運行緊，呢個 instance 退出（單實例守衛）')
    sys.exit(0)

# 窗口狀態
shown = False
_all_done_shown = False
_last_sig = None


def build_window(root):
    """建立警告視窗（右下角固定位置 — 唔遮 MT5 操作區）"""
    root.title('AI 控制中')
    root.attributes('-topmost', True)
    # 固定大小（唔自動 resize — 唔抽搐）
    W, H = 360, 400
    try:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f'{W}x{H}+{sw - W - 20}+{sh - H - 80}')
    except Exception:
        root.geometry(f'{W}x{H}+1200+580')
    root.resizable(False, False)
    # 🚨 2026-08-11：鎖死最小+最大（內容驅動自動 resize 根治 — 用戶話視窗大細抖動仲有）
    root.minsize(W, H)
    root.maxsize(W, H)
    root.overrideredirect(False)

    # 背景
    root.configure(bg='#1e1e2e')

    # 自訂 icon（emerald — 唔用 default tkinter 羽毛）
    try:
        img = tk.PhotoImage(width=32, height=32)
        for y in range(32):
            for x in range(32):
                img.put('#34d399' if (x + y) % 3 != 0 else '#1e1e2e', (x, y))
        root.iconphoto(True, img)
    except Exception:
        pass

    # 頂部色條
    bar = tk.Frame(root, bg='#34d399', height=4)
    bar.pack(fill='x')

    # 標題行
    head = tk.Frame(root, bg='#1e1e2e')
    head.pack(fill='x', padx=14, pady=(10, 2))
    tk.Label(head, text='🤖', font=('Segoe UI Emoji', 20), bg='#1e1e2e').pack(side='left')
    tk.Label(head, text='遙距控制', font=('Microsoft JhengHei', 15, 'bold'), fg='#e2e8f0', bg='#1e1e2e').pack(side='left', padx=8)

    # 操作名（併入步驟第一條 — 呢度顯示「狀態」）
    root._status_label = tk.Label(root, text='處理中…', font=('Microsoft JhengHei', 13, 'bold'), fg='#fbbf24', bg='#1e1e2e', anchor='w')
    root._status_label.pack(fill='x', padx=14, pady=(2, 2))

    # 分隔線
    tk.Frame(root, bg='#2d2d44', height=1).pack(fill='x', padx=10, pady=4)

    # 步驟列表
    root._steps_frame = tk.Frame(root, bg='#1e1e2e')
    root._steps_frame.pack(fill='both', expand=True, padx=14, pady=4)

    # 按鈕區（固定底部 — 唔亂跳）
    root._btn_frame = tk.Frame(root, bg='#1e1e2e')
    root._btn_frame.pack(fill='x', padx=14, pady=(2, 12))

    # 緊急停止（操作期間顯示）
    root._stop_btn = tk.Button(root._btn_frame, text='緊急停止', font=('Microsoft JhengHei', 12, 'bold'),
                               fg='#fff', bg='#ef4444', activebackground='#dc2626', activeforeground='#fff',
                               relief='flat', bd=0, cursor='hand2', width=10, pady=6)
    root._stop_btn.configure(command=lambda: emergency_stop(root))
    # 確定（完成後顯示 — 撳先關）
    root._done_btn = tk.Button(root._btn_frame, text='確定', font=('Microsoft JhengHei', 12, 'bold'),
                               fg='#fff', bg='#34d399', activebackground='#10b981', activeforeground='#fff',
                               relief='flat', bd=0, cursor='hand2', width=10, pady=6)
    root._done_btn.configure(command=lambda: root.withdraw())

    # 初始隱藏（等 flag）
    root.withdraw()
    return root


def emergency_stop(root):
    """緊急停止 — 寫 flag（watcher/auto_attach 會 check）+ 隱藏視窗"""
    try:
        with open(os.path.join(AGENT_DIR, '.ai_control.abort'), 'w', encoding='utf-8') as f:
            f.write('1')
        print('[alert_worker] 緊急停止已觸發', flush=True)
    except Exception:
        pass
    root.withdraw()


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
    🚨 2026-08-11 修：① 內容一樣 → skip ② 增量更新 ③ 預留固定行數（步驟加/減 — 空行填補 — 內容位置唔跳 — 用戶投訴抖動）"""
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
            # 🚨 2026-08-11 修：只喺「偏離」先修正（唔係每 round set — 之前每 round set 觸發 re-layout 抖動；唔 set 又會內容少時縮細）
            try:
                _w = root.winfo_width()
                _h = root.winfo_height()
                if _h < 400 or _w < 360:
                    root.geometry(f'360x400+{root.winfo_screenwidth() - 360 - 20}+{root.winfo_screenheight() - 400 - 80}')
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
                # 🚨 新任務偵測（flag 內容變咗 / 有 doing 步驟）→ 重置按鈕狀態
                if sig != _last_sig or has_doing:
                    _last_sig = sig
                    _all_done_shown = False
                    # 操作期間：確定隱藏 + 緊急停止顯示 + 狀態「處理中」
                    root._done_btn.pack_forget()
                    root._stop_btn.pack(fill='x')
                    root._status_label.config(text=f'執行中：{sig}', fg='#fbbf24')
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
                # flag 冇 — 視窗唔自動關（用戶撳確定先關）— 保持現狀
                if shown and _all_done_shown:
                    pass  # 保持（確定顯示 — 等用戶撳）
        except tk.TclError:
            break
        except Exception:
            continue


if __name__ == '__main__':
    # 🚨 crash log（死因記錄）
    try:
        main()
    except Exception as _e:
        try:
            import traceback as _tb
            with open(os.path.join(AGENT_DIR, 'alert_worker.log'), 'a', encoding='utf-8') as _f:
                _f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {_e}\n{_tb.format_exc()}\n")
        except Exception:
            pass
