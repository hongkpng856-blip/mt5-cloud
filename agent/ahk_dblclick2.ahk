; MT5 Cloud — AHK 模擬真實 double-click（方法 2）
; SendInput + 控制 delay（Windows 雙擊間隔內兩次 click）
#Requires AutoHotkey v2.0

x := A_Args.Length > 0 ? Integer(A_Args[1]) : 88
y := A_Args.Length > 1 ? Integer(A_Args[2]) : 258

; 確保 MT5 視窗存在（唔 activate — 淨 double-click 位置）
if !WinExist("ahk_class MetaQuotes::MetaTrader::5.00") {
    FileAppend("MT5 視窗唔存在`n", A_ScriptDir . "\ahk_test.log")
    ExitApp(1)
}

; 模擬 double-click（控制 delay — 模擬真實）
SetMouseDelay 10
MouseMove(x, y)
Sleep 100
Click(x, y)       ; 第一次 click
Sleep 100         ; double-click 間隔（Windows 雙擊 ~500ms 內）
Click(x, y)       ; 第二次 click（= double-click）
Sleep 3000

ExitApp(0)
