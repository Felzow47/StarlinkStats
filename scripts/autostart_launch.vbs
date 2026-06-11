WScript.Sleep 30000
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "F:\Dev\starlink-widget"
sh.Run """F:\Dev\starlink-widget\.venv\Scripts\pythonw.exe"" -m starlink_widget --autostart", 0, False
