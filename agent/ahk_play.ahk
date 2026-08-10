; MT5 Cloud — AHK SendMode Play double-click（事件佇列注入 — 最底層）
#Requires AutoHotkey v2.0
SendMode("Play")   ; Play 模式 — 用事件佇列（更似真實輸入）
SetMouseDelay 10

x := A_Args.Length > 0 ? Integer(A_Args[1]) : 88
y := A_Args.Length > 1 ? Integer(A_Args[2]) : 248

if !WinExist("ahk_class MetaQuotes::MetaTrader::5.00") {
    FileAppend("MT5 視窗唔存在`n", A_ScriptDir . "\ahk_test.log")
    ExitApp(1)
}

MouseMove(x, y)
Sleep 150
Click(x, y)
Sleep 100
Click(x, y)
Sleep 3000
ExitApp(0)
