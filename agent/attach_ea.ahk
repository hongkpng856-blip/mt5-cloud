#Requires AutoHotkey v2.0
#NoTrayIcon
; MT5 Navigator EA Attacher — Full AHK solution
; Usage: AutoHotkey64.exe attach_ea.ahk <EA_NAME>
; Returns: exit code 0 = success (dialog found), 1 = failed

#SingleInstance Force

eaName := A_Args.Length > 0 ? A_Args[1] : "Bollinger_Band"
logFile := "C:\Users\hongk\Desktop\mt5-cloud\agent\attach_log.txt"

Log(msg) {
    FileAppend A_Now " " msg "`n", logFile, "UTF-8"
}

Log("START: " eaName)

; Find MT5
mt5Win := WinExist("ahk_class MetaQuotes::MetaTrader::5.00")
if !mt5Win {
    Log("FAIL: MT5 not found")
    ExitApp 1
}
Log("MT5=" mt5Win)

; Activate MT5
WinActivate "ahk_id " mt5Win
WinWaitActive "ahk_id " mt5Win, 3
Sleep 300

; Get window position
WinGetPos &wx, &wy, &ww, &wh, "ahk_id " mt5Win
Log("Win: " wx "," wy " " ww "x" wh)

; ===== Step 1: Open new chart (Ctrl+N → Enter) =====
Send "^n"
Sleep 800
Send "{Enter}"
Sleep 3000
Log("Chart opened")

; ===== Step 2: Open Navigator via View menu =====
; Click "View" in menu bar
Click wx + 120 " " wy + 28
Sleep 600

; Click "Navigator" in dropdown (7th item, y ≈ 165 from top)
Click wx + 120 " " wy + 165
Sleep 1500

; Verify TreeView exists
tvHandle := 0
try {
    tvHandle := ControlGetHwnd("SysTreeView321", "ahk_id " mt5Win)
}
if !tvHandle {
    Log("FAIL: TreeView not found after Navigator toggle")
    ExitApp 1
}
Log("TV hwnd=" tvHandle)

; ===== Step 3: Expand tree and find EA =====
; Use ControlTreeView to expand and find
; Note: ControlTreeView may hang on MT5, so use keyboard navigation instead
; First click on TreeView to give it focus
ControlClick "SysTreeView321", "ahk_id " mt5Win
Sleep 500

; Press Home to go to root
Send "{Home}"
Sleep 300

; Navigate down to EA交易
; Root children order: 帳戶, 指標, EA交易, 腳本 (usually 3rd)
; Send Down 3 times to reach EA交易
Send "{Down 3}"
Sleep 500

; Expand EA交易
Send "{Right}"
Sleep 2000
Log("EA交易 expanded")

; Navigate down to target EA
; We need to count items: Advisors, Examples, Free Robots, then our EAs
; Let's search by pressing Down and checking text at each position
; Actually, just press Down until we find it
maxDowns := 40
Loop maxDowns {
    Send "{Down}"
    Sleep 100
}

; Now we need to go back up to find the EA
; Better approach: use AHK ControlTreeView
Log("Searching for " eaName "...")

; Alternative: scan TreeView with double-clicks
; Get TreeView position
ControlGetPos &tvX, &tvY, &tvW, &tvH, "SysTreeView321", "ahk_id " mt5Win
Log("TV pos: " tvX "," tvY " " tvW "x" tvH)

; Scan rows with double-click
foundIt := false
rowH := 18
Loop % tvH // rowH {
    clickY := tvY + (A_Index - 1) * rowH + 9
    clickX := tvX + 50  ; Where EA item text is
    
    ; Double-click at this row
    Click clickX " " clickY " 2"
    Sleep 2000
    
    ; Check if Properties dialog appeared (#32770 class)
    dlgWin := WinExist("ahk_class #32770")
    if dlgWin {
        dlgTitle := WinGetTitle(dlgWin)
        Log("Dialog: " dlgTitle)
        
        if InStr(dlgTitle, eaName) {
            Log("SUCCESS! " eaName " found!")
            foundIt := true
            
            ; Confirm dialog
            Send "{Enter}"
            Sleep 2000
            
            ; Enable AutoTrading
            Send "^e"
            Sleep 1000
            
            break
        } else {
            ; Wrong dialog, close
            Send "{Esc}"
            Sleep 500
        }
    }
}

if foundIt {
    Log("DONE: " eaName " attached!")
    ExitApp 0
} else {
    Log("FAIL: " eaName " not found")
    ExitApp 1
}
