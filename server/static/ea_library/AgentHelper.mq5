//+------------------------------------------------------------------+
//| AgentHelper.mq5                                                 |
//| Helper EA: reads command file, opens chart, applies template     |
//+------------------------------------------------------------------+
#property version "1.00"
#property strict

#define CMD_FILE "agent_helper.txt"

int OnInit() {
   // Heartbeat
   GlobalVariableSet("HB_AgentHelper",TimeCurrent());
   int hb_fh=FileOpen("hb_AgentHelper.txt",FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(hb_fh!=INVALID_HANDLE){FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}
   
   EventSetTimer(5);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   // Heartbeat cleanup
   GlobalVariableSet("HB_AgentHelper",0);
   int hb_fh=FileOpen("hb_AgentHelper.txt",FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(hb_fh!=INVALID_HANDLE){FileWrite(hb_fh,0);FileClose(hb_fh);}
   
   EventKillTimer();
}

void OnTimer() {
   // Heartbeat
   GlobalVariableSet("HB_AgentHelper",TimeCurrent());
   int hb_fh=FileOpen("hb_AgentHelper.txt",FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(hb_fh!=INVALID_HANDLE){FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}
   
   // Try to open command file (FileIsExist doesn't support FILE_COMMON flag in this build)
   int handle = FileOpen(CMD_FILE, FILE_READ|FILE_TXT|FILE_COMMON);
   if (handle == INVALID_HANDLE) return;
   
   string content = FileReadString(handle);
   FileClose(handle);
   
   // Parse
   string parts[3];
   int count = StringSplit(content, ',', parts);
   if (count < 3) {
      Print("AgentHelper: invalid command: " + content);
      FileDelete(CMD_FILE, FILE_COMMON);
      return;
   }
   
   string ea_name = parts[0];
   string symbol = parts[1];
   string tf_str = parts[2];
   
   Print("AgentHelper: " + ea_name + " -> " + symbol + " " + tf_str);
   
   // Convert timeframe
   ENUM_TIMEFRAMES tf = PERIOD_H1;
   if (tf_str == "M1") tf = PERIOD_M1;
   else if (tf_str == "M5") tf = PERIOD_M5;
   else if (tf_str == "M15") tf = PERIOD_M15;
   else if (tf_str == "M30") tf = PERIOD_M30;
   else if (tf_str == "H1") tf = PERIOD_H1;
   else if (tf_str == "H4") tf = PERIOD_H4;
   else if (tf_str == "D1") tf = PERIOD_D1;
   else if (tf_str == "W1") tf = PERIOD_W1;
   else if (tf_str == "MN1") tf = PERIOD_MN1;
   
   // Ensure symbol visible
   SymbolSelect(symbol, true);
   Sleep(500);
   
   // Try to open chart or use existing one
   long chart_id = ChartOpen(symbol, tf);
   if (chart_id <= 0) {
      // ChartOpen failed, scan existing charts for this symbol/tf
      long cur = ChartFirst();
      for (int i = 0; i < 100; i++) {
         if (ChartSymbol(cur) == symbol && ChartPeriod(cur) == tf) {
            chart_id = cur;
            break;
         }
         cur = ChartNext(cur);
         if (cur <= 0) break;
      }
   }
   if (chart_id <= 0) {
      Print("AgentHelper: No chart available for " + symbol);
      FileDelete(CMD_FILE, FILE_COMMON);
      return;
   }
   
   // Apply template
   string template_name = ea_name + "_" + symbol + "_" + tf_str + ".tpl";
   if (!ChartApplyTemplate(chart_id, template_name)) {
      template_name = ea_name + "_" + symbol + ".tpl";
      ChartApplyTemplate(chart_id, template_name);
   }
   
   ChartRedraw(chart_id);
   FileDelete(CMD_FILE, FILE_COMMON);
   Print("AgentHelper: done - " + ea_name);
}
//+------------------------------------------------------------------+