//+------------------------------------------------------------------+
//| TestHB_Run.mq5 — 測試：心跳運行（寫 running 心跳）              |
//| 2026-08-13 測試用（唔交易 — 淨係寫心跳）                        |
//+------------------------------------------------------------------+
#property strict
#property copyright "MT5 Cloud Test"
input string EA_Tag = "TestHB_Run";

int OnInit() { WriteHB("running"); return INIT_SUCCEEDED; }
void OnTick() { WriteHB("running"); }

void WriteHB(string status) {
   int h = FileOpen("state_TestHB_Run.json", FILE_WRITE|FILE_READ|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE) {
      FileWrite(h, "{\"status\":\"" + status + "\",\"ts\":" + (string)TimeCurrent() + "}");
      FileClose(h);
   }
}
void OnDeinit(const int reason) { }
//+------------------------------------------------------------------+
