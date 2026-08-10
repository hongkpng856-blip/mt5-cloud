#!/usr/bin/env python3
"""獨立 MT5 驗證服務 — 唔會被 Hermes reset"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import MetaTrader5 as mt5
import subprocess as sp

class VerifyHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(length))
        
        account = data.get('account', '').strip()
        password = data.get('password', '').strip()
        result = {"match": False, "local_account": "", "error": ""}
        
        try:
            r = sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, text=True, timeout=5)
            if 'terminal64' not in r.stdout:
                result = {"match": False, "error": "MT5 not running"}
            elif not account:
                result = {"match": False, "error": "No account"}
            else:
                if mt5.initialize(timeout=10000):
                    if password:
                        ok = mt5.login(int(account), password=password)
                        if ok:
                            info = mt5.account_info()
                            local = str(info.login) if info else ''
                            result = {"match": local == account, "local_account": local}
                        else:
                            # Check if already logged in with this account
                            info = mt5.account_info()
                            local = str(info.login) if info else ''
                            if local == account:
                                result = {"match": True, "local_account": local, "note": "already logged in"}
                            else:
                                result = {"match": False, "local_account": local, "error": "Password incorrect"}
                    else:
                        info = mt5.account_info()
                        local = str(info.login) if info else ''
                        result = {"match": local == account, "local_account": local}
                    mt5.shutdown()
        except Exception as e:
            result = {"match": False, "error": str(e)}
        
        self.wfile.write(json.dumps(result).encode())

print("🛡️ MT5 Verify Server :5002")
HTTPServer(('0.0.0.0', 5002), VerifyHandler).serve_forever()
