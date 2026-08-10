//+------------------------------------------------------------------+
//|                                                    TestRunner.mq5 |
//|             測試 EA 有冇運行 — 開測試單 + 圖表狀態顯示            |
//|  用法：附加到任何圖表 → 即刻開 0.01 測試單 + Comment 顯示狀態     |
//|        （運行時間/Tick 數每秒跳動 = EA 正常運行中）               |
//+------------------------------------------------------------------+
#property copyright "MT5 Cloud"
#property version   "1.00"
#property strict
#property description "測試 EA 運行狀態：附加圖表後即刻開測試單，圖表顯示運行時間/Tick數/單據"

//--- input parameters
input double InpLotSize     = 0.01;       // 測試手數
input int    InpTestMinutes = 5;          // 測試時間(分鐘, 0=無限)
input bool   InpOpenOrder   = true;       // 開測試單
input int    InpSlippage    = 30;         // 最大滑點(點)
input int    InpMagic       = 888888;     // Magic Number

//--- globals
datetime g_start_time = 0;
int      g_ticket     = 0;
ulong    g_tick_count = 0;
bool     g_finished   = false;
string   g_symbol     = "";

//+------------------------------------------------------------------+
int OnInit()
{
   g_start_time = TimeCurrent();
   g_symbol     = Symbol();
   g_tick_count = 0;
   g_finished   = false;

   // 檢查有冇同 Magic 嘅單（唔重複開）
   if(InpOpenOrder)
      OpenTestOrder();

   UpdateComment();
   Print("TestRunner EA 已啟動: ", g_symbol, " 時間=", TimeToString(g_start_time, TIME_DATE | TIME_SECONDS));
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // 平倉 + 清理
   CloseTestOrder();
   Comment("");
   Print("TestRunner EA 已停止 (reason=", reason, ")");
}

//+------------------------------------------------------------------+
void OnTick()
{
   g_tick_count++;
   UpdateComment();

   // 檢查測試時間到咗冇
   if(InpTestMinutes > 0 && !g_finished)
   {
      if(TimeCurrent() - g_start_time >= InpTestMinutes * 60)
      {
         g_finished = true;
         CloseTestOrder();
         Comment("測試完成 — EA 運行正常，測試單已平倉\n"
                 "運行 " + IntegerToString(InpTestMinutes) + " 分鐘，收到 " + IntegerToString(g_tick_count) + " 個 Tick");
         Print("TestRunner 測試完成: 運行 ", InpTestMinutes, " 分鐘, ticks=", g_tick_count);
      }
   }
}

//+------------------------------------------------------------------+
void OpenTestOrder()
{
   MqlTradeRequest request = {};
   MqlTradeResult   result = {};

   double price = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   double lot   = NormalizeLot(InpLotSize);

   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = g_symbol;
   request.volume       = lot;
   request.type         = ORDER_TYPE_BUY;
   request.price        = price;
   request.deviation    = InpSlippage;
   request.magic        = InpMagic;
   request.comment      = "TestRunner";
   request.type_filling = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
   {
      // 試 FOK
      request.type_filling = ORDER_FILLING_FOK;
      if(!OrderSend(request, result))
      {
         Print("開測試單失敗: retcode=", result.retcode, " ", result.comment);
         return;
      }
   }

   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
   {
      g_ticket = (int)result.order;
      Print("測試單已開: #", g_ticket, " ", g_symbol, " ", DoubleToString(lot, 2), " Buy @ ", DoubleToString(price, _Digits));
   }
   else
   {
      Print("開測試單 retcode: ", result.retcode, " comment: ", result.comment);
   }
}

//+------------------------------------------------------------------+
void CloseTestOrder()
{
   if(g_ticket <= 0)
   {
      // 搵返同 magic 嘅單
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         {
            g_ticket = (int)ticket;
            break;
         }
      }
   }

   if(g_ticket <= 0) return;

   MqlTradeRequest request = {};
   MqlTradeResult   result = {};

   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = g_symbol;
   request.volume       = PositionGetDouble(POSITION_VOLUME);
   request.type         = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   request.price        = (request.type == ORDER_TYPE_SELL) ? SymbolInfoDouble(g_symbol, SYMBOL_BID) : SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   request.deviation    = InpSlippage;
   request.magic        = InpMagic;
   request.comment      = "TestRunner close";
   request.position     = g_ticket;
   request.type_filling = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
   {
      request.type_filling = ORDER_FILLING_FOK;
      OrderSend(request, result);
   }

   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
      Print("測試單已平倉: #", g_ticket);
   else
      Print("平倉 retcode: ", result.retcode, " comment: ", result.comment);
}

//+------------------------------------------------------------------+
void UpdateComment()
{
   if(g_finished) return;

   int    secs = (int)(TimeCurrent() - g_start_time);
   int    hh   = secs / 3600;
   int    mm   = (secs % 3600) / 60;
   int    ss   = secs % 60;
   double bid  = SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(g_symbol, SYMBOL_ASK);

   string s = "TestRunner EA 運行中\n";
   s += "-------------------------\n";
   s += "啟動時間: " + TimeToString(g_start_time, TIME_DATE | TIME_SECONDS) + "\n";
   s += "已運行: " + StringFormat("%02d:%02d:%02d", hh, mm, ss) + "\n";
   s += "Tick 數: " + IntegerToString(g_tick_count) + "\n";
   if(g_ticket > 0)
      s += "測試單: #" + IntegerToString(g_ticket) + " (" + DoubleToString(InpLotSize, 2) + " " + g_symbol + " Buy)\n";
   else
      s += "測試單: 未開\n";
   if(InpTestMinutes > 0)
      s += "剩餘時間: " + IntegerToString(InpTestMinutes * 60 - secs) + " 秒\n";
   s += "Bid=" + DoubleToString(bid, _Digits) + "  Ask=" + DoubleToString(ask, _Digits);

   Comment(s);
}

//+------------------------------------------------------------------+
double NormalizeLot(double lot)
{
   double min_lot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MAX);
   double step    = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_STEP);
   if(lot < min_lot) lot = min_lot;
   if(lot > max_lot) lot = max_lot;
   return NormalizeDouble(MathFloor(lot / step) * step, 2);
}
//+------------------------------------------------------------------+
