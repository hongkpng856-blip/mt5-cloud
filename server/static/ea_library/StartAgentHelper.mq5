//+------------------------------------------------------------------+
//| StartAgentHelper.mq5                                            |
//| One-shot script to start AgentHelper on EURUSD H1               |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

void OnStart()
{
   Print("🚀 StartAgentHelper: opening chart...");
   
   long chart_id = ChartOpen("EURUSD", PERIOD_H1);
   if(chart_id <= 0) {
      Print("❌ StartAgentHelper: ChartOpen failed");
      return;
   }
   
   Print("✅ Chart opened: ID=" + IntegerToString(chart_id));
   
   bool applied = ChartApplyTemplate(chart_id, "AgentHelper_EURUSD_H1.tpl");
   if(applied) {
      Print("✅ AgentHelper started via ChartApplyTemplate!");
   } else {
      Print("⚠️ ChartApplyTemplate returned false");
      // Try without timeframe in name
      applied = ChartApplyTemplate(chart_id, "AgentHelper_EURUSD.tpl");
      if(applied) Print("✅ AgentHelper started (alt template)");
   }
   
   ChartRedraw(chart_id);
   Print("🏁 StartAgentHelper: done");
}
//+------------------------------------------------------------------+