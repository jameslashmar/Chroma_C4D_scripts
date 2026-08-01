@echo off
set /p timerInMins="Enter time to shutdown in minutes: "
set /A timerInSecs = %timerInMins% * 60

timeout /T %timerInSecs% & rundll32.exe powrprof.dll,SetSuspendState 0,1,0
