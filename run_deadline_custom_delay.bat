@ECHO OFF

Title Deadline Worker Delayed Startup Script by James Lashmar

echo Deadline node startup delay... 
echo:
echo Killing Deadline Worker and Launcher...
taskkill /IM deadlinelauncher.exe /f
taskkill /IM deadlineworker.exe /f
echo:
set /p timerInMins="Enter time to start worker in minutes: "
set /A timerInSecs = %timerInMins% * 60
TIMEOUT /T %timerInSecs% /NOBREAK
echo:
echo Starting Deadline Worker...
"C:\Program Files\Thinkbox\Deadline10\bin\deadlinelauncher.exe"
"C:\Program Files\Thinkbox\Deadline10\bin\deadlineworker.exe"
echo:
pause >nul