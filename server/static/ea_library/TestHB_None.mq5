//+------------------------------------------------------------------+
//| TestHB_None.mq5 — 測試：未配對（冇心跳 code）                   |
//| 2026-08-13 測試用（未部署 → 灰色未配對）                         |
//+------------------------------------------------------------------+
#property strict
#property copyright "Tradotcom Test"
input string EA_Tag = "TestHB_None";

int OnInit() { return INIT_SUCCEEDED; }
void OnTick() { }
void OnDeinit(const int reason) { }
//+------------------------------------------------------------------+
