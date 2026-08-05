@echo off
setlocal EnableExtensions

set "USB_ROOT=%~d0\"
set "ECHO_ROOT=%USB_ROOT%ECHO-7"

if not exist "%ECHO_ROOT%\echo_core\portable_launcher.py" (
    echo ECHO-7 application not found on this USB.
    exit /b 1
)

if not exist "%USB_ROOT%USB-Uncensored-LLM\Shared\bin\llama-server.exe" (
    echo llama-server.exe not found on this USB.
    exit /b 1
)

if not exist "%USB_ROOT%USB-Uncensored-LLM\Shared\models\Phi-3.5-mini-instruct-Q4_K_M.gguf" (
    echo Phi-3.5 model not found on this USB.
    exit /b 1
)

pushd "%ECHO_ROOT%"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m echo_core.portable_launcher --usb-root "%USB_ROOT%"
    set "EXITCODE=%errorlevel%"
    popd
    exit /b %EXITCODE%
)

where python >nul 2>nul
if not errorlevel 1 (
    python -m echo_core.portable_launcher --usb-root "%USB_ROOT%"
    set "EXITCODE=%errorlevel%"
    popd
    exit /b %EXITCODE%
)

popd
echo Python launcher not found.
exit /b 1
