#!/usr/bin/env python3
import sys, os, time, traceback as _tb0

# 🚨 2026-08-26：啟動即寫 log（證明 pyw 有被執行 — pythonw 靜默任何 error 都捕捉）
try:
    _log_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
    with open(os.path.join(_log_dir, "agent_launcher.log"), "a", encoding="utf-8") as _lf:
        _lf.write(f"[{time.strftime('%H:%M:%S')}] START pyw (pid={os.getpid()}) python={sys.executable}\n")
except Exception:
    pass

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception as _e_tk:
    try:
        with open(os.path.join(_log_dir, "agent_launcher.log"), "a", encoding="utf-8") as _lf:
            _lf.write(f"[{time.strftime('%H:%M:%S')}] ❌ tkinter import 失敗: {_e_tk}\n{_tb0.format_exc()}\n")
    except Exception:
        pass
    sys.exit(3)


def _log(msg):
    """寫 debug log（pythonw 靜默 — 所有階段都記低）"""
    try:
        with open(os.path.join(_log_dir, "agent_launcher.log"), "a", encoding="utf-8") as _lf:
            _lf.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

"""
Tradotcom Agent — 桌面版（double-click 安裝 + 啟動二合一）
===============================================================
- 第一次執行：安裝精靈（條款 → 檢查 → 設定 → 下載 agent.py → 自動啟動）
- 之後執行：直接啟動 Agent（綠色/紅色彈窗顯示連接狀態）

用法：double-click tradotcom_agent.pyw（或者 desktop 捷徑）
"""
import os
import sys
import time
import json
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk

APP_TITLE = "Tradotcom Agent"
DEFAULT_URL = "https://mt5cloud.esgov.org"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "agent_config.json")


# ============ 配置讀寫 ============
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ============ 檢查工具 ============
def check_mt5():
    """檢查 MT5 安裝（terminal64.exe）"""
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "MetaTrader 5", "terminal64.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "MetaTrader 5", "terminal64.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "MetaTrader 5", "terminal64.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "MetaTrader 5", "terminal64.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return True
    # 寬鬆：有 Experts 目錄就算
    mt_data = os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal")
    if os.path.isdir(mt_data):
        for d in os.listdir(mt_data):
            if os.path.isdir(os.path.join(mt_data, d, "MQL5", "Experts")):
                return True
    return False


def check_python():
    """檢查 python（py launcher / python）"""
    try:
        r = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, timeout=10)
        return True
    except Exception:
        return False


# ============ 安裝精靈（第一次） ============
class InstallWizard:
    def __init__(self, root):
        self.root = root
        self.step = 0
        self.vars = {
            "server_url": tk.StringVar(value=DEFAULT_URL),
            "agent_id": tk.StringVar(),
            "agent_token": tk.StringVar(),
            "tick": tk.BooleanVar(value=False),
        }
        self.build_welcome()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def build_welcome(self):
        self.clear()
        tk.Label(self.root, text="☁️ Tradotcom Agent 安裝精靈", font=("Segoe UI", 16, "bold")).pack(pady=20)
        # 🚨 2026-08-26：Python 3.14 警告（純文字 — 唔會卡死）
        if _check_py_version():
            tk.Label(self.root, text="⚠️ 你嘅 Python 3.14 比較新，若果 Agent 連唔到 MT5，\n建議安裝 Python 3.11/3.12（python.org）",
                     fg="#f0b90b", bg="#3d2f00", padx=10, pady=8, justify="left").pack(pady=6, padx=30)
        tk.Label(self.root, text="呢個程式會安裝 Tradotcom Agent 到你部電腦\n\n" +
                 "用途：\n"
                 "• 連接你嘅 Tradotcom 帳戶\n"
                 "• 控制你部電腦嘅 MetaTrader 5（開圖表 / 掛 EA / 刪除 EA）\n"
                 "• 上傳交易資料俾你喺網頁睇", justify="left").pack(pady=10, padx=30)
        tk.Button(self.root, text="下一步 →", command=self.build_terms, width=20,
                  bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 11, "bold")).pack(pady=15)

    def build_terms(self):
        self.clear()
        tk.Label(self.root, text="使用條款", font=("Segoe UI", 14, "bold")).pack(pady=12)
        terms = (
            "1. 本 Agent 會讀取你部電腦嘅 MT5 交易資料\n"
            "   （帳戶餘額 / 持倉 / 交易記錄），\n"
            "   並上傳至你登記嘅 Tradotcom 伺服器。\n\n"
            "2. Agent 會根據你喺網頁發出嘅指令，\n"
            "   自動操作你部電腦嘅 MT5\n"
            "   （開圖表 / 掛 EA / 刪除 EA）。\n\n"
            "3. 所有操作都會記錄喺活動日誌，\n"
            "   你隨時可以喺網頁查閱。\n\n"
            "4. 你同意只喺自己擁有嘅 MT5 帳戶使用。"
        )
        tk.Label(self.root, text=terms, justify="left", font=("Segoe UI", 10)).pack(padx=30, pady=8)
        tk.Checkbutton(self.root, text="✅ 我同意以上條款並繼續安裝", variable=self.vars["tick"],
                       font=("Segoe UI", 11)).pack(pady=10)
        btns = tk.Frame(self.root)
        btns.pack(pady=12)
        tk.Button(btns, text="← 上一步", command=self.build_welcome, width=12).pack(side="left", padx=6)
        tk.Button(btns, text="下一步 →", command=self._terms_next, width=12,
                  bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    def _terms_next(self):
        if not self.vars["tick"].get():
            messagebox.showwarning("需要同意", "請先勾選「同意條款」先可以繼續安裝")
            return
        self.build_env_check()

    def build_env_check(self):
        self.clear()
        tk.Label(self.root, text="檢查必要軟件", font=("Segoe UI", 14, "bold")).pack(pady=12)
        mt5_ok = check_mt5()
        py_ok = check_python()
        tk.Label(self.root, text="🔍 MetaTrader 5: " + ("✅ 已安裝" if mt5_ok else "❌ 未安裝"),
                 font=("Segoe UI", 11)).pack(pady=6)
        tk.Label(self.root, text="🔍 Python:       " + ("✅ 已安裝" if py_ok else "❌ 未安裝"),
                 font=("Segoe UI", 11)).pack(pady=6)
        if not mt5_ok:
            tk.Label(self.root, text="\n⚠️ 需要先安裝 MetaTrader 5（去你嘅 Broker 官網下載）",
                     fg="#f85149").pack(pady=6)
        btns = tk.Frame(self.root)
        btns.pack(pady=15)
        tk.Button(btns, text="← 上一步", command=self.build_terms, width=12).pack(side="left", padx=6)
        nxt = tk.Button(btns, text="下一步 →", width=12, bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 10, "bold"))
        nxt.pack(side="left", padx=6)
        if mt5_ok:
            nxt.config(command=self.build_config)
        else:
            nxt.config(state="disabled")

    def build_config(self):
        self.clear()
        tk.Label(self.root, text="設定伺服器與 Agent", font=("Segoe UI", 14, "bold")).pack(pady=12)
        tk.Label(self.root, text="請登入 Tradotcom 網站 → Agent 卡撳「Agent 安裝」拎 Agent ID 同 Token",
                 fg="#8b949e", font=("Segoe UI", 9)).pack(pady=4)

        frm = tk.Frame(self.root)
        frm.pack(pady=10, padx=30)
        tk.Label(frm, text="平台網址:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e", pady=5)
        tk.Entry(frm, textvariable=self.vars["server_url"], width=35, font=("Segoe UI", 10)).grid(row=0, column=1, pady=5)
        tk.Label(frm, text="Agent ID:", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e", pady=5)
        tk.Entry(frm, textvariable=self.vars["agent_id"], width=35, font=("Segoe UI", 10)).grid(row=1, column=1, pady=5)
        tk.Label(frm, text="Agent Token:", font=("Segoe UI", 10)).grid(row=2, column=0, sticky="e", pady=5)
        tk.Entry(frm, textvariable=self.vars["agent_token"], width=35, show="*", font=("Segoe UI", 10)).grid(row=2, column=1, pady=5)

        btns = tk.Frame(self.root)
        btns.pack(pady=15)
        tk.Button(btns, text="← 上一步", command=self.build_env_check, width=12).pack(side="left", padx=6)
        tk.Button(btns, text="安裝 →", command=self.do_install, width=12,
                  bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    def do_install(self):
        sid = self.vars["agent_id"].get().strip()
        tok = self.vars["agent_token"].get().strip()
        url = self.vars["server_url"].get().strip() or DEFAULT_URL
        if not sid or not tok:
            messagebox.showwarning("資料不完整", "請填 Agent ID 同 Token（喺網站 Agent 卡「Agent 安裝」度有）")
            return
        # 儲存配置
        save_config({"server_url": url, "agent_id": sid, "agent_token": tok})
        # 下載 agent.py
        self.clear()
        tk.Label(self.root, text="安裝中…", font=("Segoe UI", 14, "bold")).pack(pady=20)
        self._status = tk.Label(self.root, text="下載 agent.py…", font=("Segoe UI", 10))
        self._status.pack(pady=8)
        self.root.update()

        try:
            import urllib.request
            agent_py = os.path.join(BASE_DIR, "agent.py")
            # 🚨 2026-08-26 FIX：Cloudflare Tunnel 擋「冇 User-Agent」請求（407/403）→ 帶正常瀏覽器 UA
            _dl_url = url.rstrip("/") + "/api/agent-py"
            _dl_req = urllib.request.Request(_dl_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0",
                "Accept": "*/*",
            })
            with urllib.request.urlopen(_dl_req, timeout=30) as _dl_r:
                with open(agent_py, "wb") as _dl_f:
                    _dl_f.write(_dl_r.read())
            self._status.config(text="✅ agent.py 已下載")
            self.root.update()
        except Exception as e:
            self._status.config(text=f"❌ 下載失敗: {e}")
            self.root.update()
            messagebox.showerror("下載失敗", f"無法下載 agent.py:\n{e}\n\n請檢查平台網址同網絡")
            return

        # 安裝依賴
        self._status.config(text="安裝 Python 套件…")
        self.root.update()
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "MetaTrader5", "python-socketio[client]", "requests"],
                           timeout=180)
        except Exception as e:
            self._status.config(text=f"⚠️ 套件安裝警告: {e}")
            self.root.update()

        self._status.config(text="✅ 安裝完成！")
        self.root.update()
        # 🚨 建立桌面捷徑（double-click 開）
        try:
            self.create_desktop_shortcut()
        except Exception:
            pass
        time.sleep(0.5)
        # 自動啟動（唔使手動開 run_agent.bat）
        messagebox.showinfo("安裝完成", "✅ 安裝完成！\nAgent 而家會自動啟動…")
        self.start_agent_auto(url, sid, tok)

    def create_desktop_shortcut(self):
        """建立桌面捷徑（double-click 開 Tradotcom Agent）— 用 powershell WScript.Shell"""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            target = os.path.join(BASE_DIR, "tradotcom_agent.pyw")
            lnk = os.path.join(desktop, "Tradotcom Agent.lnk")
            icon = os.path.join(BASE_DIR, "tradotcom.ico") if os.path.exists(os.path.join(BASE_DIR, "tradotcom.ico")) else ""
            ps = (
                "$s = New-Object -ComObject WScript.Shell; "
                f"$lnk = $s.CreateShortcut('{lnk}'); "
                f"$lnk.TargetPath = '{target}'; "
                f"$lnk.WorkingDirectory = '{BASE_DIR}'; "
                + (f"$lnk.IconLocation = '{icon}'; " if icon else "")
                + "$lnk.Save()"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=20, capture_output=True)
            self._status.config(text="✅ 安裝完成 + 桌面捷徑已建立！")
            self.root.update()
        except Exception as e:
            print(f"[shortcut] {e}")

    # ============ 自動啟動 Agent ============
    def start_agent_auto(self, url, sid, tok):
        self.clear()
        tk.Label(self.root, text="啟動 Tradotcom Agent…", font=("Segoe UI", 14, "bold")).pack(pady=20)
        self._status = tk.Label(self.root, text="連接伺服器…（成功會彈綠色視窗）", font=("Segoe UI", 10))
        self._status.pack(pady=8)
        self.root.update()

        # 用 agent.py 啟動（子進程）— 佢自己會彈窗
        try:
            agent_py = os.path.join(BASE_DIR, "agent.py")
            proc = subprocess.Popen([sys.executable, "-u", agent_py,
                                     "--server", url, "--agent", sid, "--token", tok],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
            self._status.config(text=f"✅ Agent 已啟動（PID {proc.pid}）\n\n呢個視窗可以關閉 — Agent 會喺背景運行\n（綠色/紅色彈窗會話你知連接狀態）")
            self.root.update()
            # 5 秒後指引關閉
            self.root.after(3000, lambda: messagebox.showinfo(
                "Agent 已啟動",
                "✅ Tradotcom Agent 已喺背景啟動\n\n"
                "• 成功連接 → 綠色彈窗「✅ Agent 已連接」\n"
                "• 失敗 → 紅色彈窗話你知原因\n\n"
                "（下次想開 Agent — double-click 呢個程式 / 桌面捷徑即可）"))
        except Exception as e:
            self._status.config(text=f"❌ 啟動失敗: {e}")
            self.root.update()
            messagebox.showerror("啟動失敗", str(e))


# ============ 已安裝 → 直接啟動 ============
def direct_launch(cfg):
    """配置已存在 — 直接啟動 Agent（連線彈窗由 agent.py 負責）"""
    url = cfg.get("server_url", DEFAULT_URL)
    sid = cfg.get("agent_id", "")
    tok = cfg.get("agent_token", "")
    if not sid:
        return None
    try:
        agent_py = os.path.join(BASE_DIR, "agent.py")
        # 🚨 2026-08-26 FIX：啟動前確保 agent.py 係最新（舊版靜默死冇 log → 診斷唔到）
        try:
            _log("更新 agent.py...")
            import urllib.request as _ur
            _req = _ur.Request(url.rstrip("/") + "/api/agent-py", headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0"})
            with _ur.urlopen(_req, timeout=30) as _r:
                with open(agent_py, "wb") as _f:
                    _f.write(_r.read())
            _log("agent.py 已更新")
        except Exception as _e_dl:
            _log(f"agent.py 更新失敗（用舊版）: {_e_dl}")
        # 🚨 2026-08-26 FIX：確保依賴已裝（direct_launch 繞過精靈 → 可能冇 pip install）
        _log("檢查依賴...")
        try:
            import MetaTrader5  # noqa
            import socketio  # noqa
            _log("依賴 OK")
        except Exception as _e_dep:
            _log(f"依賴未裝 → pip install（{_e_dep}）")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                            "MetaTrader5", "python-socketio[client]", "requests"],
                           timeout=240)
            _log("依賴安裝完成")
        proc = subprocess.Popen([sys.executable, "-u", agent_py,
                                 "--server", url, "--agent", sid, "--token", tok],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
        return proc
    except Exception as e:
        try:
            messagebox.showerror("啟動失敗", f"無法啟動 Agent:\n{e}")
        except Exception:
            pass
        return None


# ============ Main ============
def _check_py_version():
    """檢查 Python 版本 — 3.14 太新 MetaTrader5 套件可能冇支援（第二部機案例）"""
    try:
        v = sys.version_info
        if v >= (3, 14):
            _log(f"⚠️ Python {v.major}.{v.minor} 太新 — MetaTrader5 套件可能唔支援")
            return True
    except Exception:
        pass
    return False


def main():
    # 🚨 2026-08-26：Python 3.14 警告（唔用 messagebox — mainloop 前彈會卡死；改喺精靈 welcome 頁顯示）
    root = tk.Tk()
    _log("Tk 視窗 OK")
    root.title(APP_TITLE)
    try:
        root.iconbitmap(default=os.path.join(BASE_DIR, "tradotcom.ico"))
    except Exception:
        pass
    root.geometry("520x520")
    root.configure(bg="#0b0e11")
    # 🚨 2026-08-26：確保視窗彈到最前
    root.attributes("-topmost", True)
    root.lift()
    root.update()
    _log("視窗已 lift + update")
    try:
        import tkinter.font as tkfont
        # 深色風格
        style = ttk.Style()
        style.theme_use("clam")
        root.option_add("*Background", "#0b0e11")
        root.option_add("*Foreground", "#e6e6e6")
        root.option_add("*Font", ("Segoe UI", 10))
        # 全域 Entry/Button 風格
        for w in (tk.Label, tk.Button, tk.Frame, tk.Checkbutton):
            try:
                root.option_add(f"*{w.__name__}.Background", "#0b0e11")
                root.option_add(f"*{w.__name__}.Foreground", "#e6e6e6")
            except Exception:
                pass
    except Exception:
        pass

    cfg = load_config()
    _log(f"config: {json.dumps(cfg, ensure_ascii=False)[:100]}")
    if cfg.get("agent_id"):
        # 已安裝 → 直接啟動（快閃一下即隱藏 — Agent 自己彈窗）
        _log("發現 agent_id → 直接啟動模式")
        proc = direct_launch(cfg)
        _log(f"direct_launch 返回: {proc}")
        # 🚨 FIX（2026-08-26）：agent.py 唔存在（安裝未完成）→ 唔好靜默關視窗 — 提示重裝
        if proc is None:
            _log("agent.py 唔存在 → 顯示問題提示")
            # 🚨 FIX：唔好喺 mainloop 前 messagebox（死鎖）— 用 after() 等 mainloop 開始先彈
            root.after(300, lambda: messagebox.showwarning("Agent 未安裝完成",
                "偵測到舊嘅 Agent 設定，但 agent.py 未安裝。\n\n"
                "按確定重新啟動安裝精靈。"))
            cfg = {}
        else:
            root.destroy()
            return

    _log("冇 config → 開安裝精靈")
    wizard = InstallWizard(root)
    _log("InstallWizard built — mainloop 開始")
    root.mainloop()
    _log("mainloop 返回（視窗關閉）")


if __name__ == "__main__":
    # 🚨 2026-08-26：加 debug log（pythonw 靜默 — error 唔顯示 → 寫 log 檔）
    try:
        main()
    except Exception as _e_main:
        try:
            with open(os.path.join(BASE_DIR, 'agent_launcher.log'), 'a', encoding='utf-8') as _lf:
                import traceback as _tb
                _lf.write(f"[{time.strftime('%H:%M:%S')}] ERROR: {_e_main}\n{_tb.format_exc()}\n")
        except Exception:
            pass