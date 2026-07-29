#Requires AutoHotkey v2.0
#NoTrayIcon
; Toggle MT5 Navigator panel ON (ensure visible)
; Usage: AutoHotkey64.exe nav_on.ahk
; Returns: exit code 0 = Navigator now visible, 1 = failed

mt5Win := WinExist("ahk_class MetaQuotes::MetaTrader::5.00")
if !mt5Win {
    ExitApp 1
}

; Get MT5 window position
WinGetPos &wx, &wy, &ww, &wh, "ahk_id " mt5Win

; Method: Click "View" menu → "Navigator" in dropdown
; View menu text position: approximately x=120 from left, y=30 from top
; Navigator item: approximately y=170 from top (7th item)

; First activate window
WinActivate "ahk_id " mt5Win
Sleep 300

; Click View menu
Click wx + 120 " " wy + 30
Sleep 400

; Click Navigator in dropdown
Click wx + 120 " " wy + 170
Sleep 800

ExitApp 0
