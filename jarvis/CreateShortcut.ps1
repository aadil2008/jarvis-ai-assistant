$WshShell = New-Object -ComObject WScript.Shell
$JarvisDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $JarvisDirectory "Start_Jarvis.bat"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Jarvis AI.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $JarvisDirectory
$Shortcut.IconLocation = "shell32.dll,71"
$Shortcut.Save()

Write-Host "Shortcut created at $ShortcutPath"
