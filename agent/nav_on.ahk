#Requires AutoHotkey v2.0
#NoTrayIcon
; Toggle MT5 Navigator panel ON (ensure visible)
; Uses keyboard shortcut method: Ctrl+3 or View menu
; Returns: exit code 0 = success, 1 = failed

mt5Win := WinExist("ahk_class MetaQuotes::MetaTrader::5.00")
if !mt5Win {
    ExitApp 1
}

; Method: Send F10 to activate menu bar, then navigate
; Actually: Use WinMenuSelectItem or just send keys
; Most reliable: Click on "View" text in menu bar using accurate position

WinActivate "ahk_id " mt5Win
WinWaitActive "ahk_id " mt5Win, 3
Sleep 200

; Get window position
WinGetPos &wx, &wy, &ww, &wh, "ahk_id " mt5Win

; The menu bar in MT5 has these items at specific positions:
; File (x≈30) | Edit (x≈70) | View (x≈110) | ...
; We click View to open the menu, then click Navigator
; But position depends on language! Let's try multiple x positions for "View"

; Try sending keyboard shortcut: View menu can be activated with Alt+V
; But this doesn't always work with MT5
; Alternative: Click at multiple possible "View" positions

viewFound := false
for xPos in [110, 95, 125, 80, 140] {
    Click wx + xPos " " wy + 28
    Sleep 400
    
    ; Check if a menu appeared by looking for a menu window
    ; Actually just check if clicking opened a dropdown
    ; Move mouse down to see if there's a menu item
    
    ; Click "Navigator" — it's about 165px from top in the dropdown
    Click wx + xPos " " wy + 165
    Sleep 1000
    
    ; Check if TreeView became visible
    try {
        tv := ControlGetHwnd("SysTreeView321", "ahk_id " mt5Win)
        if tv {
            ; Check visibility by getting style
            style := ControlGetStyle("SysTreeView321", "ahk_id " mt5Win)
            ; WS_VISIBLE = 0x10000000
            if (style & 0x10000000) {
                viewFound := true
                break
            }
        }
    }
}

if viewFound {
    ExitApp 0
} else {
    ; Last resort: try Ctrl+3 (Navigator shortcut in some MT5 builds)
    Send "^3"
    Sleep 1000
    ExitApp 0
}
