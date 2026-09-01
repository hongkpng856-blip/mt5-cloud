//+------------------------------------------------------------------+
//|                                                    TestRSI.mq5 |
//|             測試 EA — 持續產生真實 Trades/Win/P&L 數據            |
//|  用法：附加到任何圖表 → 自動循環開單→平倉                        |
//|        每 InpIntervalSec 秒開一單（0.10 lot）                     |
//|        持倉 InpHoldSec 秒後自動平倉 → 產生真實 profit/loss        |
//|        Trades/Win/P&L 會喺網頁配對庫即時更新                     |
//+------------------------------------------------------------------+
#property copyright "Tradotcom"
#property version   "1.00"
#property strict
#property description "Test EA (RSI style): Open every 40s, hold 30s."

//--- input parameters
input double InpLotSize      = 0.10;    // 手數
input int    InpIntervalSec  = 40;      // 開單間隔(秒)
input int    InpHoldSec      = 30;      // 持倉時間(秒)
input int    InpSlippage     = 30;      // 最大滑點(點)
input int    InpMagic        = 240708;  // Magic Number
input bool   InpAlternate    = true;    // 交替買/賣（產生 win+loss 兩邊）

//--- globals
datetime g_last_open_time = 0;
int      g_cycle          = 0;
int      g_buy_count      = 0;
int      g_sell_count     = 0;
double   g_total_profit   = 0.0;

//+------------------------------------------------------------------+
int OnInit()
{
   g_last_open_time = 0;
   g_cycle          = 0;
   g_buy_count      = 0;
   g_sell_count     = 0;
   g_total_profit   = 0.0;
   // 重啟後由 history 恢復累計 profit
   RestoreProfitFromHistory();
   // 🚨 2026-08-21：重建 trades json（掃全部歷史平倉單 — 唔會因為 EA 重啟而丟失舊單）
   RebuildTradesFile();
   EventSetTimer(1);   // 每秒檢查一次（唔靠 tick — 心跳另由系統注入 OnTick）
   WriteStats();
   Comment("TestRSI EA 已啟動 — 每 " + IntegerToString(InpIntervalSec) + " 秒開一單，持倉 " + IntegerToString(InpHoldSec) + " 秒平倉");
   Print("TestRSI EA 啟動: ", Symbol(), " lot=", DoubleToString(InpLotSize, 2), " magic=", InpMagic);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void RestoreProfitFromHistory()
{
   g_total_profit = 0;
   datetime from = TimeCurrent() - 7 * 86400;
   if(!HistorySelect(from, TimeCurrent())) return;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket <= 0) continue;
      if(HistoryDealGetInteger(deal_ticket, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetInteger(deal_ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      g_total_profit += HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
   }
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   CloseAllPositions();
   Comment("");
   Print("TestRSI EA 停止 (reason=", reason, ") 總交易=", g_cycle, " 買=", g_buy_count, " 賣=", g_sell_count);
}

//+------------------------------------------------------------------+
void OnTimer()
{
   // 1) 平倉到期單（持倉超過 InpHoldSec）
   CloseExpiredPositions();

   // 2) 開新單（距離上次開單 >= InpIntervalSec，而且冇任何「自己 magic」嘅持倉）
   if(TimeCurrent() - g_last_open_time >= InpIntervalSec && CountMyPositions() == 0)
      OpenTestOrder();
}

//+------------------------------------------------------------------+
// 心跳注入點（系統會喺呢度自動加 GlobalVariableSet + FileOpen hb_ 寫心跳）
// 唔好刪除 — 網頁「心跳運行」狀態靠呢個
void OnTick()
{
   // 心跳由系統注入 — 唔加自己 code
}

//+------------------------------------------------------------------+
int CountMyPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
void OpenTestOrder()
{
   // 揀方向（交替 or 淨買）
   bool isBuy = true;
   if(InpAlternate)
      isBuy = (g_cycle % 2 == 0);

   MqlTradeRequest request = {};
   MqlTradeResult   result = {};

   double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double lot   = NormalizeLot(InpLotSize);

   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = _Symbol;
   request.volume       = lot;
   request.type         = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   request.price        = price;
   request.deviation    = InpSlippage;
   request.magic        = InpMagic;
   request.comment      = "TestRSI";
   request.type_filling = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
   {
      request.type_filling = ORDER_FILLING_FOK;
      if(!OrderSend(request, result))
      {
         Print("開單失敗: retcode=", result.retcode, " ", result.comment);
         return;
      }
   }

   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
   {
      g_cycle++;
      g_last_open_time = TimeCurrent();
      if(isBuy) g_buy_count++;  else g_sell_count++;
      Print("📈 TestRSI 開單 #", result.order, " ", (isBuy ? "Buy" : "Sell"), " ", _Symbol, " ", DoubleToString(lot, 2), " @ ", DoubleToString(price, _Digits), " (cycle=", g_cycle, ")");
      UpdateComment();
   }
   else
   {
      Print("開單 retcode: ", result.retcode, " comment: ", result.comment);
   }
}

//+------------------------------------------------------------------+
void CloseExpiredPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
      if(TimeCurrent() - open_time < InpHoldSec) continue;

      ClosePosition(ticket);
   }
}

//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ClosePosition(ticket);
   }
}

//+------------------------------------------------------------------+
void ClosePosition(ulong ticket)
{
   MqlTradeRequest request = {};
   MqlTradeResult   result = {};

   long   pos_type = PositionGetInteger(POSITION_TYPE);
   double volume   = PositionGetDouble(POSITION_VOLUME);
   bool   isBuy    = (pos_type == POSITION_TYPE_BUY);

   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = PositionGetString(POSITION_SYMBOL);
   request.volume       = volume;
   request.type         = isBuy ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   request.price        = isBuy ? SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_BID) : SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_ASK);
   request.deviation    = InpSlippage;
   request.magic        = InpMagic;
   request.comment      = "TestRSI close";
   request.position     = ticket;
   request.type_filling = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
   {
      request.type_filling = ORDER_FILLING_FOK;
      if(!OrderSend(request, result))
      {
         Print("平倉失敗 #", ticket, ": retcode=", result.retcode, " ", result.comment);
         return;
      }
   }

   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
   {
      // 平倉後 profit 已入 history deals — 用 PositionGetDouble 攞唔到（已關）→ 直接由 deal history 累計
      double closed_profit = 0;
      // 從 history deal 攞呢個 position 嘅 profit
      if(HistorySelectByPosition(ticket))
      {
         int total = HistoryDealsTotal();
         for(int d = 0; d < total; d++)
         {
            ulong deal_ticket = HistoryDealGetTicket(d);
            if(deal_ticket > 0)
               closed_profit += HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
         }
      }
      g_total_profit += closed_profit;
      g_cycle = g_buy_count + g_sell_count + 1;   // 已平倉單計入
      Print("📉 TestRSI 平倉 #", ticket, " profit=", DoubleToString(closed_profit, 2), " 累計=", DoubleToString(g_total_profit, 2));
      UpdateComment();
      WriteStats();
      AppendTrade(ticket, closed_profit);   // 🚨 2026-08-21：記錄逐單明細（equity curve / distribution / monthly）
   }
   else
   {
      Print("平倉 retcode: ", result.retcode, " comment: ", result.comment);
   }
}

//+------------------------------------------------------------------+
// 記錄逐單明細（JSONL — 每行一單）→ trades_TestRSI.json
// 🚨 2026-08-21：俾 server 畫 equity curve / distribution / monthly P&L
void AppendTrade(ulong ticket, double profit)
{
   string fname = "trades_TestRSI.json";
   // 用 FILE_READ|FILE_WRITE 先讀後寫？唔得 — 直接 FILE_WRITE|FILE_READ append 模式
   // MQL5 冇 append flag — 用 FILE_READ|FILE_WRITE 定位到檔尾
   int fh = FileOpen(fname, FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON);
   if(fh != INVALID_HANDLE)
   {
      FileSeek(fh, 0, SEEK_END);
      string line = StringFormat("{\"ticket\":%I64d,\"time\":%I64d,\"profit\":%.2f}\n", ticket, (long)TimeCurrent(), profit);
      FileWriteString(fh, line);
      FileClose(fh);
   }
}

//+------------------------------------------------------------------+
// 重建 trades json — 掃全部歷史平倉單（EA 重啟後唔丟失舊單）
// 🚨 2026-08-21：OnInit 時 call — 確保 trades json 有完整歷史（唔係淨係新單）
void RebuildTradesFile()
{
   string fname = "trades_TestRSI.json";
   string all = "";
   datetime from = TimeCurrent() - 7 * 86400;   // 最近 7 日
   if(HistorySelect(from, TimeCurrent()))
   {
      int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
      {
         ulong deal_ticket = HistoryDealGetTicket(i);
         if(deal_ticket <= 0) continue;
         if(HistoryDealGetInteger(deal_ticket, DEAL_MAGIC) != InpMagic) continue;
         if(HistoryDealGetInteger(deal_ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;  // 只計平倉
         double profit = HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
         if(profit == 0) continue;
         datetime deal_time = (datetime)HistoryDealGetInteger(deal_ticket, DEAL_TIME);
         all += StringFormat("{\"ticket\":%I64d,\"time\":%I64d,\"profit\":%.2f}\n",
                             deal_ticket, (long)deal_time, profit);
      }
   }
   if(all == "") return;   // 冇數據唔好清空現有
   int fh = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if(fh != INVALID_HANDLE)
   {
      FileWriteString(fh, all);
      FileClose(fh);
   }
}

//+------------------------------------------------------------------+
// 寫統計落 state_TestRSI.json（detector 讀呢個檔判斷運行狀態 + 我加 stats）
// 路徑：Common/Files/state_<EA>.json
// 🚨 2026-08-21：加 win_sum/loss_sum（贏嘅總額/輸嘅總額 — 準確計 avg win/loss）
void WriteStats()
{
   string fname = "state_TestRSI.json";
   int wins = 0, losses = 0;
   double win_sum = 0, loss_sum = 0;
   ScanHistoryStats(wins, losses, win_sum, loss_sum);
   string json = StringFormat("{\"ea\":\"TestRSI\",\"status\":\"running\",\"ts\":%I64d,\"trades\":%d,\"wins\":%d,\"losses\":%d,\"profit\":%.2f,\"win_sum\":%.2f,\"loss_sum\":%.2f}",
                              (long)TimeCurrent(), wins + losses, wins, losses, g_total_profit, win_sum, loss_sum);
   int fh = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_COMMON);
   if(fh != INVALID_HANDLE)
   {
      FileWriteString(fh, json);
      FileClose(fh);
   }
}

//+------------------------------------------------------------------+
// 由 MT5 history deals 掃呢個 magic 嘅已平倉單（準確 trades/wins/losses + win_sum/loss_sum）
void ScanHistoryStats(int &wins, int &losses, double &win_sum, double &loss_sum)
{
   wins = 0;
   losses = 0;
   win_sum = 0;
   loss_sum = 0;
   datetime from = TimeCurrent() - 7 * 86400;   // 最近 7 日
   if(!HistorySelect(from, TimeCurrent())) return;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket <= 0) continue;
      if(HistoryDealGetInteger(deal_ticket, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetInteger(deal_ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;  // 只計平倉
      double profit = HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
      if(profit > 0) { wins++; win_sum += profit; }
      else if(profit < 0) { losses++; loss_sum += profit; }
   }
}

//+------------------------------------------------------------------+
void UpdateComment()
{   string s = "TestRSI EA 運行中\n";
   s += "-------------------------\n";
   s += "已開單: " + IntegerToString(g_cycle) + " (買 " + IntegerToString(g_buy_count) + " / 賣 " + IntegerToString(g_sell_count) + ")\n";
   s += "累計 P&L: " + DoubleToString(g_total_profit, 2) + "\n";
   s += "Magic: " + IntegerToString(InpMagic) + "\n";
   s += "每 " + IntegerToString(InpIntervalSec) + "s 一單 / 持倉 " + IntegerToString(InpHoldSec) + "s\n";
   Comment(s);
}

//+------------------------------------------------------------------+
double NormalizeLot(double lot)
{
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lot < min_lot) lot = min_lot;
   if(lot > max_lot) lot = max_lot;
   return NormalizeDouble(MathFloor(lot / step) * step, 2);
}
//+------------------------------------------------------------------+
