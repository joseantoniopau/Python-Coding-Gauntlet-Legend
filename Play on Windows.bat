@echo off
REM Double-click to play. Finds Python, then hands over to run.py.
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (
    py -3 run.py
    goto done
)
where python >nul 2>nul && (
    python run.py
    goto done
)

echo.
echo   Python was not found on this machine.
echo.
echo   Install Python 3.11 or newer from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" in the installer, then run this again.
echo.
pause
exit /b 1

:done
if errorlevel 1 pause
endlocal
