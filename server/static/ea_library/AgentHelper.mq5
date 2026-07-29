//+------------------------------------------------------------------+
//| AgentHelper.mq5                                                 |
//| Helper EA: reads command file, opens chart, applies template     |
//+------------------------------------------------------------------+
#property version "1.00"
#property strict

#define CMD_FILE "agent_helper.txt"

int OnInit() {
   EventSetTimer(5);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   EventKillTimer();
}

void OnTimer() {
   // Check for command file
   if (!FileIsExist(CMD_FILE)) return;
   
   // Read command: "EA_NAME,SYMBOL,TIMEFRAME"
   int handle = FileOpen(CMD_FILE, FILE_READ|FILE_TXT|FILE_ANSI);
   if (handle == INVALID_HANDLE) return;
   
   string content = FileReadString(handle);
   FileClose(handle);
   
   // Parse
   string parts[3];
   int count = StringSplit(content, ',', parts);
   if (count < 3) {
      Print("AgentHelper: invalid command: " + content);
      FileDelete(CMD_FILE);
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
   
   // Open chart
   long chart_id = ChartOpen(symbol, tf);
   if (chart_id <= 0) {
      Print("AgentHelper: ChartOpen failed for " + symbol);
      FileDelete(CMD_FILE);
      return;
   }
   Sleep(1000);
   
   // Apply template
   string template_name = ea_name + "_" + symbol + "_" + tf_str + ".tpl";
   if (!ChartApplyTemplate(chart_id, template_name)) {
      // Try without timeframe
      template_name = ea_name + "_" + symbol + ".tpl";
      ChartApplyTemplate(chart_id, template_name);
   }
   
   ChartRedraw(chart_id);
   FileDelete(CMD_FILE);
   Print("AgentHelper: done - " + ea_name);
}
//+------------------------------------------------------------------+