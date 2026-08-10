; MT5 Cloud — ControlClick double-click 測試（AHK v2）
; 試：後台向 Navigator tree 發 double-click（唔需要 MT5 最前）
#Requires AutoHotkey v2.0

; 參數：x y（tree 相對座標）
x := A_Args.Length > 0 ? Integer(A_Args[1]) : 88
y := A_Args.Length > 1 ? Integer(A_Args[2]) : 258

; 方法 1: ControlClick（後台 — 直接向控制項發訊息）
try {
    ControlClick("x" . x . " y" . y, "ahk_class MetaQuotes::MetaTrader::5.00", , "Left", 2)
    Sleep(3000)
    ToolTip("ControlClick 完成 (" . x . "," . y . ")")
    Sleep(2000)
    ToolTip()
} catch as e {
    FileAppend("ControlClick 錯誤: " . e.Message . "`n", A_ScriptDir . "\ahk_test.log")
    ExitApp(1)
}
ExitApp(0)
