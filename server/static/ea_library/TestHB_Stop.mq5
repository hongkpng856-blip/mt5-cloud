//+------------------------------------------------------------------+
//| TestHB_Stop.mq5 — 測試：沒有心跳（寫 stopped）                  |
//| 2026-08-13 測試用（模擬 EA 停咗 — 紅色沒有心跳）                |
//+------------------------------------------------------------------+
#property strict
#property copyright "MT5 Cloud Test"
input string EA_Tag = "TestHB_Stop";

int OnInit() { WriteHB("stopped"); return INIT_SUCCEEDED; }
void OnTick() { WriteHB("stopped"); }

void WriteHB(string status) {
   int h = FileOpen("state_TestHB_Stop.json", FILE_WRITE|FILE_READ|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE) {
      FileWrite(h, "{\"status\":\"" + status + "\",\"ts\":" + (string)TimeCurrent() + "}");
      FileClose(h);
   }
}
void OnDeinit(const int reason) { }
//+------------------------------------------------------------------+
