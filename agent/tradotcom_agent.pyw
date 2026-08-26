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
# 🚨 2026-08-26：固定安裝位置（唔使估喺邊 — launcher 會放呢度）
_FIXED_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "TradotcomAgent")
_my_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.normpath(_my_dir) != os.path.normpath(_FIXED_DIR):
    try:
        os.makedirs(_FIXED_DIR, exist_ok=True)
        import shutil as _sh
        for _f in os.listdir(_my_dir):
            if _f.endswith((".pyw", ".py", ".json", ".log", ".bat", ".ico")):
                _src = os.path.join(_my_dir, _f)
                _dst = os.path.join(_FIXED_DIR, _f)
                if os.path.isfile(_src) and not os.path.exists(_dst):
                    _sh.copy2(_src, _dst)
    except Exception:
        pass
BASE_DIR = _FIXED_DIR
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
        tk.Label(self.root, text="Tradotcom Agent Setup Wizard", font=("Segoe UI", 16, "bold")).pack(pady=20)
        # 🚨 2026-08-26：Python 3.14 警告（純文字 — 唔會卡死）
        if _check_py_version():
            tk.Label(self.root, text="Your Python 3.14 is very new - if Agent can't connect to MT5,\ninstall Python 3.11/3.12 (python.org)",
                     fg="#f0b90b", bg="#3d2f00", padx=10, pady=8, justify="left").pack(pady=6, padx=30)
        tk.Label(self.root, text="This program installs Tradotcom Agent on this computer\n\n" +
                 "用途：\n"
                 "• 連接你嘅 Tradotcom 帳戶\n"
                 "• 控制你部電腦嘅 MetaTrader 5（開圖表 / 掛 EA / 刪除 EA）\n"
                 "• 上傳交易資料俾你喺網頁睇", justify="left").pack(pady=10, padx=30)
        tk.Button(self.root, text="Next ->", command=self.build_terms, width=20,
                  bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 11, "bold")).pack(pady=15)

    def build_terms(self):
        self.clear()
        tk.Label(self.root, text="Terms of Use", font=("Segoe UI", 14, "bold")).pack(pady=12)
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
        tk.Checkbutton(self.root, text="I agree to the terms above and continue", variable=self.vars["tick"],
                       font=("Segoe UI", 11)).pack(pady=10)
        btns = tk.Frame(self.root)
        btns.pack(pady=12)
        tk.Button(btns, text="<- Back", command=self.build_welcome, width=12).pack(side="left", padx=6)
        tk.Button(btns, text="Next ->", command=self._terms_next, width=12,
                  bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    def _terms_next(self):
        if not self.vars["tick"].get():
            messagebox.showwarning("Agreement Required", "Please tick 'I agree to the terms' first to continue")
            return
        self.build_env_check()

    def build_env_check(self):
        self.clear()
        tk.Label(self.root, text="Checking Required Software", font=("Segoe UI", 14, "bold")).pack(pady=12)
        mt5_ok = check_mt5()
        py_ok = check_python()
        tk.Label(self.root, text="🔍 MetaTrader 5: " + ("Installed" if mt5_ok else "Not installed"),
                 font=("Segoe UI", 11)).pack(pady=6)
        tk.Label(self.root, text="🔍 Python:       " + ("Installed" if py_ok else "Not installed"),
                 font=("Segoe UI", 11)).pack(pady=6)
        if not mt5_ok:
            tk.Label(self.root, text="\n[WARNING] Install MetaTrader 5 first (download from your broker's website)",
                     fg="#f85149").pack(pady=6)
        btns = tk.Frame(self.root)
        btns.pack(pady=15)
        tk.Button(btns, text="<- Back", command=self.build_terms, width=12).pack(side="left", padx=6)
        nxt = tk.Button(btns, text="Next ->", width=12, bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 10, "bold"))
        nxt.pack(side="left", padx=6)
        if mt5_ok:
            nxt.config(command=self.build_config)
        else:
            nxt.config(state="disabled")

    def build_config(self):
        self.clear()
        tk.Label(self.root, text="Server and Agent Settings", font=("Segoe UI", 14, "bold")).pack(pady=12)
        tk.Label(self.root, text="Log in to Tradotcom website -> Agent card -> 'Agent Install' to get Agent ID and Token",
                 fg="#8b949e", font=("Segoe UI", 9)).pack(pady=4)

        frm = tk.Frame(self.root)
        frm.pack(pady=10, padx=30)
        tk.Label(frm, text="Server URL:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e", pady=5)
        tk.Entry(frm, textvariable=self.vars["server_url"], width=35, font=("Segoe UI", 10)).grid(row=0, column=1, pady=5)
        tk.Label(frm, text="Agent ID:", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e", pady=5)
        tk.Entry(frm, textvariable=self.vars["agent_id"], width=35, font=("Segoe UI", 10)).grid(row=1, column=1, pady=5)
        tk.Label(frm, text="Agent Token:", font=("Segoe UI", 10)).grid(row=2, column=0, sticky="e", pady=5)
        tk.Entry(frm, textvariable=self.vars["agent_token"], width=35, show="*", font=("Segoe UI", 10)).grid(row=2, column=1, pady=5)

        btns = tk.Frame(self.root)
        btns.pack(pady=15)
        tk.Button(btns, text="<- Back", command=self.build_env_check, width=12).pack(side="left", padx=6)
        tk.Button(btns, text="Install ->", command=self.do_install, width=12,
                  bg="#f0b90b", fg="#0b0e11", font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)

    def do_install(self):
        sid = self.vars["agent_id"].get().strip()
        tok = self.vars["agent_token"].get().strip()
        url = self.vars["server_url"].get().strip() or DEFAULT_URL
        if not sid or not tok:
            messagebox.showwarning("Incomplete Data", "Please fill in Agent ID and Token (available in the website Agent card -> 'Agent Install')")
            return
        # 儲存配置
        save_config({"server_url": url, "agent_id": sid, "agent_token": tok})
        # 下載 agent.py
        self.clear()
        tk.Label(self.root, text="Installing...", font=("Segoe UI", 14, "bold")).pack(pady=20)
        self._status = tk.Label(self.root, text="Downloading agent.py...", font=("Segoe UI", 10))
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
            self._status.config(text="agent.py downloaded")
            self.root.update()
        except Exception as e:
            self._status.config(text=f"Download failed: {e}")
            self.root.update()
            messagebox.showerror("Download Failed", f"Cannot download agent.py:\n{e}\n\nCheck the server URL and network")
            return

        # 安裝依賴
        self._status.config(text="Installing Python packages...")
        self.root.update()
        try:
            # 🚨 2026-08-26 FIX：用「執行 agent 嗰個 Python」（3.11/3.12）裝套件 — 唔用 pyw 自己（可能 3.14/uv — 唔一致）
            _pip_py = _pick_good_python()
            subprocess.run([_pip_py, "-m", "pip", "install", "-q", "MetaTrader5", "python-socketio[client]", "requests", "pystray", "pillow"],
                           timeout=180)
        except Exception as e:
            self._status.config(text=f"[WARNING] Package install warning: {e}")
            self.root.update()

        self._status.config(text="Installation complete!")
        self.root.update()
        # 🚨 建立桌面捷徑（double-click 開）
        try:
            self.create_desktop_shortcut()
        except Exception:
            pass
        time.sleep(0.5)
        # 自動啟動（唔使手動開 run_agent.bat）
        messagebox.showinfo("Installation Complete", "Installation complete!\nAgent will start automatically...")
        self.start_agent_auto(url, sid, tok)

    def create_desktop_shortcut(self):
        """建立桌面捷徑（double-click 開 Tradotcom Agent — 指向 launcher 完整流程）"""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            # 🚨 2026-08-26 FIX：指向 launcher.bat（唔係 pyw）— launcher 會更新 pyw + agent.py + 啟動
            _lnk_bat = os.path.join(BASE_DIR, "tradotcom_launcher.bat")
            # 🚨 FIX：launcher 可能唔喺固定 folder（用戶喺 Downloads 下載）→ 自動下載去固定位置
            if not os.path.isfile(_lnk_bat):
                try:
                    _log("Downloading launcher.bat...")
                    import urllib.request as _ur3
                    _req3 = _ur3.Request("https://mt5cloud.esgov.org/api/agent-download", headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0"})
                    with _ur3.urlopen(_req3, timeout=20) as _r3:
                        with open(_lnk_bat, "wb") as _f3:
                            _f3.write(_r3.read())
                    _log("launcher.bat downloaded")
                except Exception as _e3:
                    _log(f"launcher download failed: {_e3}")
            if not os.path.isfile(_lnk_bat):
                _lnk_bat = os.path.join(BASE_DIR, "tradotcom_agent.pyw")  # fallback
            target = _lnk_bat
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
            self._status.config(text="Installation Complete + Desktop Shortcut Created!")
            self.root.update()
        except Exception as e:
            print(f"[shortcut] {e}")

    # ============ 自動啟動 Agent ============
    def start_agent_auto(self, url, sid, tok):
        self.clear()
        tk.Label(self.root, text="Starting Tradotcom Agent...", font=("Segoe UI", 14, "bold")).pack(pady=20)
        self._status = tk.Label(self.root, text="Connecting to server... (green popup = success)", font=("Segoe UI", 10))
        self._status.pack(pady=8)
        self.root.update()

        # 用 agent.py 啟動（子進程）— 佢自己會彈窗
        try:
            agent_py = os.path.join(BASE_DIR, "agent.py")
            _py_exe = _pick_good_python()
            proc = subprocess.Popen([_py_exe, "-u", agent_py,
                                     "--server", url, "--agent", sid, "--token", tok],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
            self._status.config(text=f"Agent started (PID {proc.pid})\n\nYou can close this window - Agent runs in background\n(green/red popup shows connection status)")
            self.root.update()
            # 5 秒後指引關閉
            self.root.after(3000, lambda: messagebox.showinfo(
                "Agent 已啟動",
                "✅ Tradotcom Agent 已喺背景啟動\n\n"
                "• 成功連接 → 綠色彈窗「✅ Agent 已連接」\n"
                "• 失敗 → 紅色彈窗話你知原因\n\n"
                "（下次想開 Agent — double-click 呢個程式 / 桌面捷徑即可）"))
        except Exception as e:
            self._status.config(text=f"Start failed: {e}")
            self.root.update()
            messagebox.showerror("Start Failed", str(e))


# ============ 已Install -> 直接啟動 ============
def _pick_good_python():
    """🚨 2026-08-26：揀 Python 執行 agent.py — 3.11/3.12 優先（MetaTrader5 最穩）
    Python 3.14 唔兼容（import 卡死）→ 唔好用。返回 python.exe 路徑。
    """
    cands = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python311", "python.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "python.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python313", "python.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Python311", "python.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Python312", "python.exe"),
    ]
    for c in cands:
        if os.path.isfile(c):
            _log(f"用 Python: {c}")
            return c
    # fallback 當前（唔理想 — 3.14 可能卡）
    if sys.version_info >= (3, 14):
        _log("⚠️ 冇 3.11/3.12 — 用當前 Python（3.14 可能卡 MetaTrader5）")
    return sys.executable


def _pick_good_python():
    """🚨 2026-08-26：揀 Python 執行 agent.py — 3.11/3.12 優先（MetaTrader5 最穩）
    Python 3.14 唔兼容（import 卡死）→ 唔好用。返回 python.exe 路徑。
    """
    cands = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python311", "python.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "python.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python313", "python.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Python311", "python.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Python312", "python.exe"),
    ]
    for c in cands:
        if os.path.isfile(c):
            _log(f"用 Python: {c}")
            return c
    if sys.version_info >= (3, 14):
        _log("⚠️ 冇 3.11/3.12 — 用當前 Python（3.14 可能卡 MetaTrader5）")
    return sys.executable


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
        # 🚨 2026-08-26 FIX v2：依賴唔齊 → 唔喺背景 pip install（卡 240 秒用戶睇唔到）
        # → 直接返回 None → main() 轉去安裝精靈（用戶睇到進度 + 有正式安裝流程）
        _log("檢查依賴...")
        _py_exe = _pick_good_python()
        try:
            # 用目標 Python（3.11/3.12）檢查依賴 — 唔用 pyw 自己（3.14 import 會卡死）
            _chk = subprocess.run([_py_exe, "-c", "import MetaTrader5, socketio"],
                                  capture_output=True, timeout=15)
            if _chk.returncode == 0:
                _log("依賴 OK")
            else:
                _log(f"依賴唔齊（{_chk.stderr.decode('utf-8', 'ignore')[:80]}）→ 轉安裝精靈")
                return None
        except Exception as _e_dep2:
            _log(f"依賴檢查失敗（{_e_dep2}）→ 轉安裝精靈")
            return None
        proc = subprocess.Popen([_py_exe, "-u", agent_py,
                                 "--server", url, "--agent", sid, "--token", tok],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
        return proc
    except Exception as e:
        try:
            messagebox.showerror("Start Failed", f"Cannot start Agent:\n{e}")
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


def _self_update():
    """pyw auto-update: download latest version and overwrite self (next launch = new version)
    Desktop shortcut points to old pyw -> self-update on every start
    """
    try:
        _log("Checking pyw update...")
        import urllib.request as _ur2
        _req = _ur2.Request("https://mt5cloud.esgov.org/api/agent-pyw", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0"})
        with _ur2.urlopen(_req, timeout=15) as _r:
            _new = _r.read()
        _me = os.path.abspath(__file__)
        import hashlib as _hl
        if len(_new) > 10000:  # valid pyw (>10KB)
            try:
                with open(_me, "rb") as _f0:
                    _cur = _f0.read()
            except Exception:
                _cur = b""
            # 🚨 FIX：hash 一樣 = 已經係最新 → 唔重啟（防無限循環）
            if _hl.md5(_cur).hexdigest() == _hl.md5(_new).hexdigest():
                _log("pyw already latest (no restart)")
            else:
                with open(_me, "wb") as _f:
                    _f.write(_new)
                _log("pyw updated - restarting with new version")
                subprocess.Popen([sys.executable, _me], cwd=os.path.dirname(_me))
                os._exit(0)
    except Exception as _e_su:
        _log(f"pyw update failed (using current): {_e_su}")


def main():
    # Python 3.14 warning shown in wizard welcome page (not messagebox - avoids deadlock)
    _self_update()
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
        # 已Install -> 直接啟動（快閃一下即隱藏 — Agent 自己彈窗）
        _log("發現 agent_id → 直接啟動模式")
        proc = direct_launch(cfg)
        _log(f"direct_launch 返回: {proc}")
        # 🚨 FIX（2026-08-26）：agent.py 唔存在（安裝未完成）→ 唔好靜默關視窗 — 提示重裝
        if proc is None:
            _log("agent.py 唔存在 → 顯示問題提示")
            # FIX: don't call messagebox before mainloop (deadlock) - use after()
            root.after(300, lambda: messagebox.showwarning("Agent Not Installed",
                "Old Agent config detected but agent.py not installed.\n\n"
                "Press OK to restart the setup wizard."))
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