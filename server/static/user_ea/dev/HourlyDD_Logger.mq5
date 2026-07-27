//+------------------------------------------------------------------+
//|                                         HourlyDD_Logger_local.mq5|
//|        Records equity drawdown each hour to CSV in MQL5\Files    |
//+------------------------------------------------------------------+
#property copyright "MyTools_EA"
#property version   "1.01"
#property strict

//--- global variables
datetime lastHourRecorded = 0;
double   highWaterMark    = 0.0;
double   maxDrawdown      = 0.0;
ulong    accountNumber    = 0;
string   fileName         = "";

//+------------------------------------------------------------------+
//| Expert initialization                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   // set initial equity & account id
   highWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
   accountNumber = AccountInfoInteger(ACCOUNT_LOGIN);

   // build a timestamped CSV filename
   MqlDateTime dt; 
   TimeToStruct(TimeCurrent(), dt);
   string ts = StringFormat("%04d%02d%02d_%02d%02d",
                            dt.year, dt.mon, dt.day,
                            dt.hour, dt.min);
   fileName = StringFormat("HourlyEquityDD_%I64u_%s.csv",
                           accountNumber, ts);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Tick handler                                                    |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1) Update metrics every tick
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance    = AccountInfoDouble(ACCOUNT_BALANCE);

   // High-Water-Mark of equity
   if(equity > highWaterMark)
      highWaterMark = equity;

   // Drawdown = balance – equity, floored at zero
   double drawdown = equity - balance;
   if(drawdown > 0.0)
      drawdown = 0.0;

   // Max drawdown observed so far
   if(drawdown < maxDrawdown)
      maxDrawdown = drawdown;

   // 2) Only record once at the top of each hour
   if(dt.min != 0 || lastHourRecorded == dt.hour)
      return;

   // format timestamp & each metric
   string lineTS       = StringFormat("%04d.%02d.%02d %02d:%02d",
                                      dt.year, dt.mon, dt.day,
                                      dt.hour, dt.min);
   string strEquity    = DoubleToString(equity,       2);
   string strBalance   = DoubleToString(balance,      2);
   string strHWM       = DoubleToString(highWaterMark,2);
   string strDrawdown  = DoubleToString(drawdown,     2);
   string strMaxDD     = DoubleToString(maxDrawdown,  2);

   // new columns: margin used & free margin
   double marginUsed  = AccountInfoDouble(ACCOUNT_MARGIN);
   double freeMargin  = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   string strMargin   = DoubleToString(marginUsed,    2);
   string strFree     = DoubleToString(freeMargin,    2);

   // open (or create) CSV file, append new line
   int fh = FileOpen(
      fileName,
      FILE_CSV
    | FILE_READ
    | FILE_WRITE
    | FILE_SHARE_READ
    | FILE_SHARE_WRITE
    | FILE_ANSI,
      ','
   );
   if(fh == INVALID_HANDLE)
   {
      PrintFormat("Failed to open %s : %d", fileName, GetLastError());
   }
   else
   {
      // write header if file is empty
      if(FileSize(fh) == 0)
         FileWrite(fh,
                   "Timestamp",
                   "Equity",
                   "Balance",
                   "HighWaterMark",
                   "Drawdown",
                   "MaxDrawdown",
                   "MarginUsed",
                   "FreeMargin");

      // append one line
      FileSeek(fh, 0, SEEK_END);
      FileWrite(fh,
                lineTS,
                strEquity,
                strBalance,
                strHWM,
                strDrawdown,
                strMaxDD,
                strMargin,
                strFree);
      FileFlush(fh);
      FileClose(fh);

      // console log
      PrintFormat("Logged %s | EQ=%.2f | BAL=%.2f | HWM=%.2f | DD=%.2f | MaxDD=%.2f | MRG=%.2f | FM=%.2f",
                  lineTS,
                  equity,
                  balance,
                  highWaterMark,
                  drawdown,
                  maxDrawdown,
                  marginUsed,
                  freeMargin);
   }

   // mark this hour done
   lastHourRecorded = dt.hour;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // nothing to clean up (files always closed immediately)
}
