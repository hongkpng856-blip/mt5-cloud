//+------------------------------------------------------------------+
//| TestHB_Start.mq5 — 測試：等待心跳（冇心跳 code）                |
//| 2026-08-13 測試用（部署後有熱鍵但唔寫心跳 → 黃色等待心跳）       |
//+------------------------------------------------------------------+
#property strict
#property copyright "MT5 Cloud Test"
input string EA_Tag = "TestHB_Start";

int OnInit() { return INIT_SUCCEEDED; }
void OnTick() { }
void OnDeinit(const int reason) { }
//+------------------------------------------------------------------+
