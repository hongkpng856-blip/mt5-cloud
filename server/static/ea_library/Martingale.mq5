//+------------------------------------------------------------------+
//| Martingale.mq5                                                 |
//| 測試用 EA #19 - 馬丁格爾              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #19"
#property version        "1.00"
#property description    "馬丁格爾"
#property description    "輸時加倍注碼"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240019; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Martingale 已啟動！策略：馬丁格爾");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Martingale 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("馬丁格爾\n輸時加倍注碼\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
