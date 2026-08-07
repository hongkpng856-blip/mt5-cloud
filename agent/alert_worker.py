"""獨立警告視窗 process（2026-08-07：根治 Tcl_AsyncDelete crash）
原本 tkinter 喺 watcher 入面嘅獨立 thread — Python 退出時 crash（async handler deleted by wrong thread）
而家：獨立 subprocess — watcher 唔再 import tkinter — 唔會 crash
機制：讀 flag 檔（.ai_control.show）— 有 → 顯示視窗；冇 → 隱藏"""
import os
import sys
import time
import tkinter as tk

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHOW_FLAG = os.path.join(AGENT_DIR, '.ai_control.show')

root = None
window = None


def build_window():
    global root, window
    root = tk.Tk()
    window = root
    root.title("AI 控制中")
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.98)
    root.configure(bg="#18181b")
    # emerald 頂條
    tk.Frame(root, bg="#10b981", height=4).pack(fill="x")
    window._prog_label = tk.Label(root, text="🤖 AI 控制中", bg="#18181b", fg="#fafafa",
             font=("Microsoft JhengHei UI", 16, "bold"))
    window._prog_label.pack(pady=(12, 4))
    tk.Label(root, text="請勿使用滑鼠及鍵盤…", bg="#18181b", fg="#a1a1aa",
             font=("Microsoft JhengHei UI", 11)).pack(pady=(0, 6))
    # 警告
    tk.Label(root, text="⚠️ 如非必要請勿操作電腦", bg="#18181b", fg="#fbbf24",
             font=("Microsoft JhengHei UI", 10)).pack(pady=(0, 10))
    root.withdraw()  # 初始隱藏
    # 放右下角
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w, h = 320, 150
    root.geometry(f"{w}x{h}+{sw - w - 24}+{sh - h - 60}")


def main():
    build_window()
    shown = False
    last_prog = ''
    while True:
        try:
            has_flag = os.path.isfile(SHOW_FLAG)
            if has_flag:
                # 🚨 每次 poll 都讀 flag 更新程式名（唔理 shown 狀態 — 連續操作唔會顯示舊名）
                try:
                    with open(SHOW_FLAG, 'r', encoding='utf-8') as f:
                        prog = f.read().strip() or 'AI 控制中'
                    if prog != last_prog:
                        window._prog_label.config(text=prog)
                        last_prog = prog
                except Exception:
                    pass
                if not shown:
                    window_state = root.state()
                    if window_state == 'withdrawn':
                        root.deiconify()
                    else:
                        root.lift()
                    shown = True
            elif not has_flag and shown:
                root.withdraw()
                shown = False
            root.update()
        except Exception:
            pass
        time.sleep(0.5)


if __name__ == '__main__':
    main()
