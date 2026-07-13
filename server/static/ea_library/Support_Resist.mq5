//+------------------------------------------------------------------+
//| Support_Resist.mq5                                                 |
//| 測試用 EA #13 - 支持阻力突破              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #13"
#property version        "1.00"
#property description    "支持阻力突破"
#property description    "通道突破策略"

input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240013; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Support_Resist 已啟動！策略：支持阻力突破");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Support_Resist 已停止");
}

void OnTick()
{
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("支持阻力突破\n通道突破策略\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
