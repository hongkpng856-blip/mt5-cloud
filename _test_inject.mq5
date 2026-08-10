//+------------------------------------------------------------------+
//| Bollinger_Band.mq5                                                 |
//| 測試用 EA #05 - 保力加通道              |
//+------------------------------------------------------------------+
#property copyright      "測試策略 #05"
#property version        "1.00"
#property description    "保力加通道"
#property description    "BB(20,2) 突破上下軌"

//+------------------------------------------------------------------+
//| 控制層（自動注入 — 網頁操控 EA）                                |
//| 指令檔: Common/Files/ctrl_<EA名>.json  {"cmd":"stop"}            |
//| 狀態檔: Common/Files/state_<EA名>.json 心跳（running/stopped）   |
//+------------------------------------------------------------------+
string __mt5c_ctrl_file   = "ctrl_"  + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
string __mt5c_state_file  = "state_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
datetime __mt5c_last_beat = 0;

void __mt5c_write_state(string status) {
   int h = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if (h != INVALID_HANDLE) {
      FileWrite(h, StringFormat("{\"ea\":\"%s\",\"status\":\"%s\",\"ts\":%d}",
               MQLInfoString(MQL_PROGRAM_NAME), status, (int)TimeCurrent()));
      FileClose(h);
   }
}

void __mt5c_process() {
   if (FileIsExist(__mt5c_ctrl_file, FILE_COMMON)) {
      int h = FileOpen(__mt5c_ctrl_file, FILE_READ|FILE_TXT|FILE_COMMON);
      if (h != INVALID_HANDLE) {
         string c = FileReadString(h);
         FileClose(h);
         FileDelete(__mt5c_ctrl_file, FILE_COMMON);
         if (StringFind(c, "stop") >= 0 || StringFind(c, "pause") >= 0) {
            __mt5c_write_state("stopped");
            ExpertRemove();
            return;
         }
      }
   }
   if (TimeCurrent() - __mt5c_last_beat >= 5) {
      __mt5c_write_state("running");
      __mt5c_last_beat = TimeCurrent();
   }
}


input double LotSize     = 0.01;     // 每單手數
input int    MagicNumber = 20240005; // EA ID
input bool   EnableLog   = true;     // 啟用日誌

int OnInit()
{
   if(EnableLog) Print("✅ Bollinger_Band 已啟動！策略：保力加通道");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(EnableLog) Print("🛑 Bollinger_Band 已停止");
}

void OnTick()
{
   __mt5c_process();
   static datetime lastBar = 0;
   if(TimeCurrent() - lastBar < 60) return;
   lastBar = TimeCurrent();

   Comment("保力加通道\nBB(20,2) 突破上下軌\nMagic: " + IntegerToString(MagicNumber) + "\n狀態：等待交易信號");
}
//+------------------------------------------------------------------+
