//+------------------------------------------------------------------+
//| Parabolic_SAR.mq5                                                 |
//| 測試用 EA #10 - SAR 轉向              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #10"
#property version        "1.00"
#property description    "SAR 轉向"
#property description    "SAR(0.02,0.2)"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240010; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Parabolic_SAR 已啟動！策略：SAR 轉向");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Parabolic_SAR 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("SAR 轉向\nSAR(0.02,0.2)\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
