//+------------------------------------------------------------------+
//| TestHB_Run.mq5 — 測試：心跳運行（OnTimer 每秒寫心跳）           |
//| 2026-08-14 測試用（每秒心跳 — 更即時偵測）                      |
//+------------------------------------------------------------------+
#property strict
#property copyright "MT5 Cloud Test"
input string EA_Tag = "TestHB_Run";

int OnInit() {
   EventSetTimer(1);  // 🚨 2026-08-14：每秒心跳（OnTimer — 唔受 tick 影響 — 市場收市都寫）
   WriteHB("running");
   return INIT_SUCCEEDED;
}
void OnTimer() { WriteHB("running"); }  // 每秒寫心跳
void OnTick() { }

void WriteHB(string status) {
   int h = FileOpen("state_TestHB_Run.json", FILE_WRITE|FILE_READ|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE) {
      FileWrite(h, "{\"status\":\"" + status + "\",\"ts\":" + (string)TimeCurrent() + "}");
      FileClose(h);
   }
}
void OnDeinit(const int reason) { EventKillTimer(); }
//+------------------------------------------------------------------+
