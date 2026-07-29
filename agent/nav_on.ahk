#Requires AutoHotkey v2.0
#NoTrayIcon
; Reliable MT5 Navigator toggle — v2
; Checks parent window visibility, not just TreeView style

mt5Hwnd := WinExist("ahk_class MetaQuotes::MetaTrader::5.00")
if !mt5Hwnd {
    ExitApp 1
}
WinActivate "ahk_id " mt5Hwnd
Sleep 300
WinGetPos &wx, &wy, &ww, &wh, "ahk_id " mt5Hwnd

IsNavVisible() {
    ; Check if TreeView has a visible parent by checking its position
    ; If Navigator is hidden, the TreeView is at a negative/off-screen position
    try {
        ctrlHwnd := ControlGetHwnd("SysTreeView321", "ahk_class MetaQuotes::MetaTrader::5.00")
        if !ctrlHwnd
            return false
        ; Check if the control is actually visible by getting its window rect
        ; Use WinGetPos for the control
        ; A visible TreeView in a maximized MT5 window has rect like (0, 436)-(390, 724)
        ; A hidden one has very different coordinates
        ControlGetPos &cx, &cy, &cw, &ch, "SysTreeView321", "ahk_class MetaQuotes::MetaTrader::5.00"
        ; If the control is visible on screen (positive coordinates within window bounds)
        return (cx >= 0 && cx < ww && cy > 0 && cy < wh && cw > 10 && ch > 10)
    }
    return false
}

; Method 1: Click menu bar at View positions
for x in [85, 95, 105, 115, 125, 135] {
    Click wx + x " " wy + 20
    Sleep 300
    Click wx + x " " wy + 150
    Sleep 800
    if IsNavVisible()
        ExitApp 0
}

; Method 2: Ctrl+3
Send "^3"
Sleep 1000
if IsNavVisible()
    ExitApp 0

; Method 3: Alt+V, n, Enter
Send "!v"
Sleep 400
Send "n"
Sleep 400
Send "{Enter}"
Sleep 800
if IsNavVisible()
    ExitApp 0

ExitApp 1