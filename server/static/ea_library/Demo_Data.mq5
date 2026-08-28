//+------------------------------------------------------------------+
//| Demo_Data.mq5 — 即刻數據展示 EA（Tradotcom 平台）               |
//| 部署後即刻產生：心跳 + 模擬交易記錄 + 即時指標數值              |
//+------------------------------------------------------------------+
#property copyright "Tradotcom"
#property version   "1.00"
#property strict

input string InpSymbol = "";           // 交易品種（部署時自動寫入）
input int    MagicNumber = 240710;     // Magic Number
input double LotSize = 1.00;           // 手數
input int    DataInterval = 30;        // 數據間隔（秒）
input bool   UseDemoData = true;       // 使用模擬數據（演示用）

// ---- Tradotcom 心跳（自動注入 2026-08-14 — 每秒寫心跳 + 暫停指令檢查）----
string __mt5c_ctrl_file = "";
string __mt5c_state_file = "";
void __mt5c_process() {
   if(__mt5c_ctrl_file == "") {
      __mt5c_ctrl_file = "ctrl_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
      __mt5c_state_file = "state_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
   }
   // 開目標圖表（只開一次）
   static bool __mt5c_chart_done = false;
   if(!__mt5c_chart_done) {
      __mt5c_chart_done = true;
      if(InpSymbol != "" && Symbol() != InpSymbol) {
         long _cid = ChartOpen(InpSymbol, PERIOD_CURRENT);
         if(_cid > 0) { ChartSetInteger(_cid, CHART_BRING_TO_TOP, 0, true); Print("📈 已開目標圖表: ", InpSymbol); }
      }
   }
   // 暫停指令
   if(FileIsExist(__mt5c_ctrl_file, FILE_COMMON)) {
      int h = FileOpen(__mt5c_ctrl_file, FILE_READ|FILE_TXT|FILE_COMMON);
      if(h != INVALID_HANDLE) {
         string c = FileReadString(h);
         FileClose(h);
         FileDelete(__mt5c_ctrl_file, FILE_COMMON);
         if(StringFind(c, "stop") >= 0) {
            int h2 = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
            if(h2 != INVALID_HANDLE) { FileWrite(h2, "{\"status\":\"stopped\"}"); FileClose(h2); }
            ExpertRemove();
            return;
         }
      }
   }
   // 心跳
   int h = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE) {
      FileWrite(h, StringFormat("{\"ea\":\"%s\",\"status\":\"running\",\"ts\":%d}", MQLInfoString(MQL_PROGRAM_NAME), (int)TimeCurrent()));
      FileClose(h);
   }
}
// ---- 心跳結束 ----

// 模擬交易記錄檔（後備 CSV）
string __demo_trade_file = "demo_trades_" + MQLInfoString(MQL_PROGRAM_NAME) + ".csv";

// 模擬交易（每 DataInterval 秒一筆 — 開倉 + 平倉對 — 有真 P&L）
void __demo_trade() {
   static datetime lastTrade = 0;
   if(TimeCurrent() - lastTrade < DataInterval) return;
   lastTrade = TimeCurrent();

   string sym = InpSymbol != "" ? InpSymbol : Symbol();
   if(SymbolInfoInteger(sym, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_DISABLED) return;

   // 1. 先搵有冇未平倉（我哋嘅 magic）— 有就平倉（攞 P&L）
   bool closed = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != sym) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      // 平倉
      MqlTradeRequest req = {};
      MqlTradeResult res = {};
      req.action = TRADE_ACTION_DEAL;
      req.symbol = sym;
      req.volume = PositionGetDouble(POSITION_VOLUME);
      req.type = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      req.position = ticket;
      req.price = req.type == ORDER_TYPE_SELL ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);
      req.deviation = 30;
      req.magic = MagicNumber;
      req.comment = "Demo_Data 平倉";
      if(OrderSend(req, res)) {
         double profit = PositionGetDouble(POSITION_PROFIT);
         Print("✅ 平倉: ", ticket, " 利潤=", profit);
         closed = true;
      } else {
         Print("❌ 平倉失敗: ", res.retcode);
      }
      break;  // 每次只處理一單
   }
   // 2. 冇未平倉 → 開新倉
   if(!closed) {
      bool buy = (MathRand() % 2 == 0);
      double lot = LotSize;
      double price = buy ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
      if(price <= 0) return;
      MqlTradeRequest req = {};
      MqlTradeResult res = {};
      req.action = TRADE_ACTION_DEAL;
      req.symbol = sym;
      req.volume = lot;
      req.type = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      req.price = price;
      req.deviation = 30;
      req.magic = MagicNumber;
      req.comment = "Demo_Data 模擬交易";
      if(OrderSend(req, res)) {
         Print("✅ 開倉: ", buy ? "BUY" : "SELL", " ", sym, " ", lot, " @ ", price);
      } else {
         Print("❌ 開倉失敗: ", res.retcode, " ", res.comment);
      }
   }
}

// 即時指標數值（Comment 顯示）
void __demo_comment() {
   string sym = InpSymbol != "" ? InpSymbol : Symbol();
   double atr = iATR(sym, PERIOD_H1, 14, 0);
   double rsi = iRSI(sym, PERIOD_H1, 14, PRICE_CLOSE, 0);
   double ma  = iMA(sym, PERIOD_H1, 20, 0, MODE_SMA, PRICE_CLOSE, 0);
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK);

   Comment(
      "📊 Demo_Data — 即時數據展示\n",
      "───────────────\n",
      "Symbol: ", sym, "  Bid: ", DoubleToString(bid, 5), "  Ask: ", DoubleToString(ask, 5), "\n",
      "ATR(14): ", DoubleToString(atr, 5), "  RSI(14): ", DoubleToString(rsi, 2), "\n",
      "MA(20): ", DoubleToString(ma, 5), "\n",
      "───────────────\n",
      "模擬交易: 每 ", IntegerToString(DataInterval), " 秒一筆\n",
      "交易記錄: demo_trades_", MQLInfoString(MQL_PROGRAM_NAME), ".csv\n",
      "Magic: ", IntegerToString(MagicNumber), "\n",
      "狀態: 🟢 運行中（心跳 + 數據輸出）"
   );
}

int OnInit() {
   MathSrand(GetTickCount());
   Print("🚀 Demo_Data 啟動: ", Symbol(), " Magic=", MagicNumber);
   __demo_process();  // 即刻寫心跳
   return(INIT_SUCCEEDED);
}

void OnTick() {
   __mt5c_process();   // 心跳
   __demo_trade();     // 模擬交易
   __demo_comment();   // 即時指標
}

void OnTimer() {
   __mt5c_process();
   __demo_trade();
}

void OnDeinit(const int reason) {
   Comment("");
}
//+------------------------------------------------------------------+
