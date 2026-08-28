//+------------------------------------------------------------------+
//| Equity protection EA corrected with optional TerminalClose       |
//+------------------------------------------------------------------+
#property copyright "Revised"
#property version   "1.34"
#include <Trade\Trade.mqh>

input double  InpDrawdownPercent         = 5.0;
input double  InpMinEquity               = 10000.0;
input ulong   InpDeviationPoints         = 50;
input bool    InpLogVerbose              = true;

// New inputs for terminal-close behavior
input bool    InpCloseTerminalAfterProtection = true; // if true, set stop flag and close terminal after protection
input int     InpWaitAfterFlagMs             = 500;  // ms to wait after setting GlobalVariable before closing

CTrade trade;
double highWater = 0.0;
double drawdownPercent = 0.0;
double minEquity = 0.0;
bool   protectionTriggered = false;

//+------------------------------------------------------------------+
int OnInit()
  {
   drawdownPercent = InpDrawdownPercent;
   minEquity       = InpMinEquity;

   if(drawdownPercent <= 0.0) drawdownPercent = 5.0;
   if(minEquity < 0.0) minEquity = 0.0;

   highWater = AccountInfoDouble(ACCOUNT_EQUITY);
   if(InpLogVerbose) PrintFormat("Init: highWater=%.2f DD=%.2f%% minEquity=%.2f",
                                 highWater, drawdownPercent, minEquity);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(InpLogVerbose) PrintFormat("Deinit: reason=%d highWater=%.2f minEquity=%.2f", reason, highWater, minEquity);
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   // If protection already triggered, do nothing further here
   if(protectionTriggered) return;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > highWater)
     {
      highWater = equity;
      if(InpLogVerbose) PrintFormat("New highWater=%.2f", highWater);
     }

   double threshold = highWater * (1.0 - drawdownPercent/100.0);
   if(equity <= threshold && equity >= minEquity)
     {
      if(InpLogVerbose) PrintFormat("Equity %.2f <= threshold %.2f -> closing positions", equity, threshold);
      CloseOpenPositions();
      // mark protection triggered so we don't re-run
      protectionTriggered = true;
     }
  }
//+------------------------------------------------------------------+
void CloseOpenPositions()
  {
   // Safety: maximum iterations to avoid accidental infinite loops
   int safety = 200;

   // Loop while there are positions and safety counter not exhausted
   while(PositionsTotal() > 0 && safety-- > 0)
     {
      int total = PositionsTotal();
      // iterate by index from last to first to avoid index shifting
      int idx = total - 1;
      if(idx < 0) break;

      // Get ticket by index; this also selects the position for PositionGet* calls
      ulong ticket = PositionGetTicket(idx);
      if(ticket == 0)
        {
         if(InpLogVerbose) PrintFormat("PositionGetTicket(%d) returned 0, skipping", idx);
         // small pause to avoid tight loop if selection repeatedly fails
         Sleep(50);
         continue;
        }

      // Read symbol and volume from the selected position
      string symbol = PositionGetString(POSITION_SYMBOL);
      double volume = PositionGetDouble(POSITION_VOLUME);

      // Reset error and attempt close
      ResetLastError();
      bool closed = trade.PositionClose(ticket, InpDeviationPoints);
      if(!closed)
        {
         int err = GetLastError();
         PrintFormat("Failed to close ticket=%I64u symbol=%s volume=%.2f error=%d",
                     ticket, symbol, volume, err);

         // Generic wait on failure to avoid tight retry loops
         Sleep(200);
        }
      else
        {
         PrintFormat("Closed ticket=%I64u symbol=%s volume=%.2f", ticket, symbol, volume);
         // Give the terminal a short time to process the close and update positions/equity
         Sleep(100);
        }
     }

   // Update equity-related variables after closing attempts
   double equityAfterClose = AccountInfoDouble(ACCOUNT_EQUITY);
   minEquity = equityAfterClose;
   highWater = equityAfterClose;

   if(InpLogVerbose)
     {
      PrintFormat("After closing: equity=%.2f -> minEquity updated to %.2f, highWater updated to %.2f",
                  equityAfterClose, minEquity, highWater);
     }

   // If configured, set persistent stop flag and close terminal
   if(InpCloseTerminalAfterProtection)
     {
      const string flagName = "GLOBAL_EA_TRADING";
      // set persistent flag to 0 so EAs that honor it will not trade after restart
      bool flagSet = GlobalVariableSet(flagName, 0);
      if(InpLogVerbose) PrintFormat("GlobalVariable '%s' set to 0 (trading disabled) -> %s", flagName, flagSet ? "OK" : "FAILED");

      // small wait to ensure the variable is persisted
      Sleep(MathMax(0, InpWaitAfterFlagMs));

      // final log then close terminal
      if(InpLogVerbose) Print("Calling TerminalClose(0) to exit the terminal now.");
      bool ok = TerminalClose(0);
      if(!ok)
        {
         Print("TerminalClose returned false. Check logs and permissions.");
        }
      // If TerminalClose succeeds, the terminal will exit and code will stop here.
     }
  }
//+------------------------------------------------------------------+
