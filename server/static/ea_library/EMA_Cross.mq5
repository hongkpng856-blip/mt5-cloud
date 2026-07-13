//+------------------------------------------------------------------+
//| EMA_Cross.mq5                                                 |
//| 測試用 EA #02 - 指數平均線交叉              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #02"
#property version        "1.00"
#property description    "指數平均線交叉"
#property description    "EMA(12) x EMA(26)"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240002; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ EMA_Cross 已啟動！策略：指數平均線交叉");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 EMA_Cross 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("指數平均線交叉\nEMA(12) x EMA(26)\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
