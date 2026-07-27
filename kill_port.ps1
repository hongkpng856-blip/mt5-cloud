$port = 5000
$conn = netstat -ano | Select-String ":${port}\s" | Select-String "LISTENING"
if ($conn) {
    $procId = $conn.Line.Trim().Split()[-1]
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Write-Output "Killed PID $procId on port $port"
} else {
    Write-Output "No process on port $port"
}
Start-Sleep -Seconds 2
