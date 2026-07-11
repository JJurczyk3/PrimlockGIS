@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo 错误：无法打开 Primelock GIS 应用文件夹。
    echo 请将完整解压后的文件夹移动到普通本地目录，然后重试。
    pause
    exit /b 2
)

if not exist "%~dp0app\PrimelockGIS.exe" (
    echo 错误：缺少 PrimelockGIS.exe。
    echo 请先完整解压 ZIP 文件，再运行此启动程序。
    popd
    pause
    exit /b 2
)

"%~dp0app\PrimelockGIS.exe" launch --language zh-CN
set "PRIMELOCK_EXIT=%ERRORLEVEL%"
popd

if not "%PRIMELOCK_EXIT%"=="0" (
    echo.
    echo Primelock GIS 无法启动。错误代码：%PRIMELOCK_EXIT%
    echo 请运行 app\PrimelockGIS.exe doctor --language zh-CN 查看诊断详情。
    pause
)

exit /b %PRIMELOCK_EXIT%
