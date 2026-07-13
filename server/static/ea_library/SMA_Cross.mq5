//+------------------------------------------------------------------+
//| SMA_Cross.mq5 — 真正嘅移動平均線交叉 EA                         |
//| 策略：SMA(10) 升穿 SMA(30) → 買入                               |
//|       SMA(10) 跌穿 SMA(30) → 賣出                               |
//+------------------------------------------------------------------+
#property copyright      "你的第一個演算法交易 EA"
#property version        "1.10"
#property description    "SMA 黃金交叉買入 / 死亡交叉賣出"
#property description    "每支新 K 線檢查一次，唔會每個 tick 都 trade"

//+------------------------------------------------------------------+
//| 你可以喺 MT5 嘅 EA 設定入面改呢啲參數                           |
//+------------------------------------------------------------------+
input double   LotSize        = 0.01;        // 每單手數 (0.01 = 迷你)
input int      FastMA         = 10;           // 快線周期
input int      SlowMA         = 30;           // 慢線周期
input int      StopLoss_Pts   = 200;          // 止蝕 (點數)
input int      TakeProfit_Pts = 400;          // 止賺 (點數)
input int      MagicNumber    = 240701;       // EA 識別碼

//+------------------------------------------------------------------+
//| 全局變數                                                         |
//+------------------------------------------------------------------+
int      fastHandle, slowHandle;   // MA 指標 handle
double   fastBuf[], slowBuf[];     // MA 數值 buffer
datetime lastBarTime = 0;          // 記錄上一支 K 線時間

//+------------------------------------------------------------------+
//| Expert initialization function — EA 啟動時執行一次               |
//+------------------------------------------------------------------+
int OnInit()
{
   // 建立 MA 指標
   fastHandle = iMA(_Symbol, _Period, FastMA, 0, MODE_SMA, PRICE_CLOSE);
   slowHandle = iMA(_Symbol, _Period, SlowMA, 0, MODE_SMA, PRICE_CLOSE);

   if(fastHandle == INVALID_HANDLE || slowHandle == INVALID_HANDLE)
   {
      Print("❌ 建立 MA 指標失敗！");
      return(INIT_FAILED);
   }

   Print("✅ SMA_Cross 已啟動！");
   Print("   品種: ", _Symbol, " | 週期: ", EnumToString(_Period));
   Print("   快線: SMA(", FastMA, ") | 慢線: SMA(", SlowMA, ")");
   Print("   每單 ", LotSize, " 手 | 止蝕 ", StopLoss_Pts, " 點 | 止賺 ", TakeProfit_Pts, " 點");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function — EA 停止時執行                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Comment("");  // 清空螢幕顯示
   Print("🛑 SMA_Cross 已停止 (原因: ", reason, ")");
}

//+------------------------------------------------------------------+
//| Expert tick function — 每次價格跳動都會執行                      |
//+------------------------------------------------------------------+
void OnTick()
{
   // ===== 每支 K 線只檢查一次，慳 CPU =====
   if(TimeCurrent() - lastBarTime < PeriodSeconds(_Period))
      return;
   lastBarTime = TimeCurrent();

   // ===== 獲取 MA 數值 =====
   ArraySetAsSeries(fastBuf, true);
   ArraySetAsSeries(slowBuf, true);

   if(CopyBuffer(fastHandle, 0, 0, 3, fastBuf) < 3) return;
   if(CopyBuffer(slowHandle, 0, 0, 3, slowBuf) < 3) return;

   // ===== 檢查現有持倉 =====
   bool hasBuy  = false;
   bool hasSell = false;
   ulong buyTicket = 0, sellTicket = 0;

   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         {
            if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
            {
               hasBuy = true;
               buyTicket = ticket;
            }
            else if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
            {
               hasSell = true;
               sellTicket = ticket;
            }
         }
      }
   }

   // ===== 策略邏輯 =====
   // 條件: fast[1]=最新完成嘅K線, fast[2]=前一支
   // 黃金交叉: 快線[1] > 慢線[1] AND 快線[2] <= 慢線[2]
   // 死亡交叉: 快線[1] < 慢線[1] AND 快線[2] >= 慢線[2]

   bool goldenCross  = (fastBuf[1] > slowBuf[1] && fastBuf[2] <= slowBuf[2]);
   bool deathCross   = (fastBuf[1] < slowBuf[1] && fastBuf[2] >= slowBuf[2]);

   // --- 黃金交叉 → 買入 ---
   if(goldenCross)
   {
      Print("🔔 黃金交叉！", _Symbol, " Fast=", DoubleToString(fastBuf[1], _Digits),
            " Slow=", DoubleToString(slowBuf[1], _Digits));

      // 如果有賣倉，先平倉
      if(hasSell)
      {
         ClosePosition(sellTicket, "死亡交叉平賣倉");
         hasSell = false;
      }

      // 如果冇買倉，開買倉
      if(!hasBuy)
      {
         OpenOrder(ORDER_TYPE_BUY);
      }
   }
   // --- 死亡交叉 → 賣出 ---
   else if(deathCross)
   {
      Print("🔔 死亡交叉！", _Symbol, " Fast=", DoubleToString(fastBuf[1], _Digits),
            " Slow=", DoubleToString(slowBuf[1], _Digits));

      // 如果有買倉，先平倉
      if(hasBuy)
      {
         ClosePosition(buyTicket, "死亡交叉平買倉");
         hasBuy = false;
      }

      // 如果冇賣倉，開賣倉
      if(!hasSell)
      {
         OpenOrder(ORDER_TYPE_SELL);
      }
   }

   // ===== 顯示狀態 =====
   string status = "SMA_Cross 運行中 🟢\n";
   status += "快線 SMA(" + (string)FastMA + "): " + DoubleToString(fastBuf[1], _Digits) + "\n";
   status += "慢線 SMA(" + (string)SlowMA + "): " + DoubleToString(slowBuf[1], _Digits) + "\n";
   status += "差距: " + DoubleToString(fastBuf[1] - slowBuf[1], _Digits) + "\n";
   status += "持倉: " + (hasBuy ? "📈 買" : "") + (hasSell ? "📉 賣" : "無") + "\n";
   status += "Magic: " + (string)MagicNumber;
   Comment(status);
}

//+------------------------------------------------------------------+
//| 開倉函數                                                         |
//+------------------------------------------------------------------+
void OpenOrder(ENUM_ORDER_TYPE type)
{
   MqlTradeRequest req = {};
   MqlTradeResult  res = {};

   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = _Symbol;
   req.volume    = LotSize;
   req.magic     = MagicNumber;
   req.deviation = 10;  // 滑點容忍

   // 計算價格
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(type == ORDER_TYPE_BUY)
   {
      req.type  = ORDER_TYPE_BUY;
      req.price = ask;
      req.sl    = NormalizeDouble(ask - StopLoss_Pts * point, _Digits);
      req.tp    = NormalizeDouble(ask + TakeProfit_Pts * point, _Digits);
   }
   else
   {
      req.type  = ORDER_TYPE_SELL;
      req.price = bid;
      req.sl    = NormalizeDouble(bid + StopLoss_Pts * point, _Digits);
      req.tp    = NormalizeDouble(bid - TakeProfit_Pts * point, _Digits);
   }

   if(OrderSend(req, res))
   {
      Print("✅ 開倉成功！Ticket: ", res.order, " 類型: ", EnumToString(type));
   }
   else
   {
      Print("❌ 開倉失敗！錯誤碼: ", res.retcode, "  ", GetLastErrorMsg(res.retcode));
   }
}

//+------------------------------------------------------------------+
//| 平倉函數                                                         |
//+------------------------------------------------------------------+
void ClosePosition(ulong ticket, string reason)
{
   if(!PositionSelectByTicket(ticket))
   {
      Print("❌ 平倉失敗：找不到持倉 ", ticket);
      return;
   }

   MqlTradeRequest req = {};
   MqlTradeResult  res = {};

   req.action   = TRADE_ACTION_DEAL;
   req.symbol   = PositionGetString(POSITION_SYMBOL);
   req.volume   = PositionGetDouble(POSITION_VOLUME);
   req.magic    = MagicNumber;
   req.position = ticket;
   req.deviation = 10;

   ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double profit = PositionGetDouble(POSITION_PROFIT);

   if(type == POSITION_TYPE_BUY)
   {
      req.type  = ORDER_TYPE_SELL;
      req.price = bid;
   }
   else
   {
      req.type  = ORDER_TYPE_BUY;
      req.price = ask;
   }

   if(OrderSend(req, res))
   {
      Print("✅ 平倉成功！", reason, " 利潤: $", DoubleToString(profit, 2));
   }
   else
   {
      Print("❌ 平倉失敗！錯誤碼: ", res.retcode);
   }
}

//+------------------------------------------------------------------+
//| 錯誤碼轉文字 MQL5 冇內置，簡單版                                |
//+------------------------------------------------------------------+
string GetLastErrorMsg(int code)
{
   // 常見錯誤
   switch(code)
   {
      case 10004: return "交易伺服器繁忙";
      case 10006: return "沒有連線";
      case 10007: return "速度太快";
      case 10008: return "價格變咗";
      case 10014: return "無足夠保證金";
      case 10015: return "無足夠資金";
      case 10016: return "禁止交易";
      case 10019: return "市場關閉";
      case 10021: return "已過期";
      default:    return "未知錯誤";
   }
}
//+------------------------------------------------------------------+
