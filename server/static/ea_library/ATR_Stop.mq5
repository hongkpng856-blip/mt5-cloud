//+------------------------------------------------------------------+
//| ATR_Stop.mq5                                                 |
//| 測試用 EA #08 - ATR 追蹤止損              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #08"
#property version        "1.00"
#property description    "ATR 追蹤止損"
#property description    "ATR(14) x 3 追蹤"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240008; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ ATR_Stop 已啟動！策略：ATR 追蹤止損");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 ATR_Stop 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("ATR 追蹤止損\nATR(14) x 3 追蹤\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
