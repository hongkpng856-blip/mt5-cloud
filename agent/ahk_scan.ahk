; MT5 Cloud — AHK 掃描 double-click（幾個位置試）
#Requires AutoHotkey v2.0

start_x := Integer(A_Args[1])
start_y := Integer(A_Args[2])

SetMouseDelay 5
Loop 8 {
    y := start_y + (A_Index - 1) * 8
    MouseMove(start_x, y)
    Sleep 50
    Click(start_x, y)
    Sleep 80
    Click(start_x, y)
    Sleep 1200
}
ExitApp(0)
