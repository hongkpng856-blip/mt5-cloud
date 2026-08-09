#!/usr/bin/env python3
"""
Deploy Notification — AI 控制中視窗
顯示「🤖 AI 正在控制 MT5，請勿操作」提示
🚨 2026-08-10：根治 Tcl crash — 唔再用 tkinter（喺 worker thread 開 Tk → Tcl_AsyncDelete crash → worker thread 死 → watcher 掛起）
→ 改做純 print 記錄（alert_worker 獨立 process 已經顯示「AI 控制中」警告視窗 — 呢個係重複舊機制）
"""
import sys


def show(message="🤖 AI 正在控制 MT5\n請勿使用滑鼠及鍵盤", duration=None):
    """顯示控制中（🚨 2026-08-10：no-op — 唔開 tkinter — alert_worker 已顯示警告視窗）"""
    try:
        print(f"[deploy_notify] AI 控制中: {message.splitlines()[0]}")
        sys.stdout.flush()
    except Exception:
        pass


def hide():
    """關閉控制中（🚨 2026-08-10：no-op — 唔開 tkinter）"""
    try:
        print("[deploy_notify] 控制結束")
        sys.stdout.flush()
    except Exception:
        pass


if __name__ == '__main__':
    show("測試通知視窗", duration=3)
    hide()
    print("done")
