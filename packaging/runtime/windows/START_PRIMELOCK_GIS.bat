@echo off
setlocal EnableExtensions DisableDelayedExpansion

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Could not open the Primelock GIS application folder.
    echo Move the extracted folder to a normal local location and try again.
    pause
    exit /b 2
)

if not exist "%~dp0app\PrimelockGIS.exe" (
    echo ERROR: PrimelockGIS.exe is missing.
    echo Extract the complete ZIP before running this launcher.
    popd
    pause
    exit /b 2
)

"%~dp0app\PrimelockGIS.exe" launch --language en
set "PRIMELOCK_EXIT=%ERRORLEVEL%"
popd

if not "%PRIMELOCK_EXIT%"=="0" (
    echo.
    echo Primelock GIS could not be started. Error code: %PRIMELOCK_EXIT%
    echo Run app\PrimelockGIS.exe doctor --language en for diagnostic details.
    pause
)

exit /b %PRIMELOCK_EXIT%
