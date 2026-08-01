@echo off
set /p timerInMins="Enter time to shutdown in minutes: "
set /A timerInSecs = %timerInMins% * 60

timeout /T %timerInSecs% & shutdown -s
