@echo off
echo.
echo ========================================================
echo      Elysius Whitelist Client - Build Script
echo ========================================================
echo.

echo [INFO] Verificando Python...
call python --version
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    pause
    exit /b 1
)

echo [INFO] Criando ambiente virtual...
if not exist "venv" call python -m venv venv

echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo [INFO] Instalando dependencias...
call pip install --upgrade pip
call pip install pystray Pillow requests pyinstaller

echo [INFO] Criando icone...
if not exist "icon.ico" call python create_icon.py

echo [INFO] Limpando builds anteriores...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo.
echo [INFO] Compilando executavel (pode demorar)...
echo.

call pyinstaller --onefile --noconsole --clean --name "ElysiusWhitelist" --icon "icon.ico" --hidden-import pystray._win32 --hidden-import PIL._tkinter_finder --add-data "icon.ico;." --version-file version_info.txt whitelist_client.py

if exist "dist\ElysiusWhitelist.exe" (
    echo.
    echo ========================================================
    echo              BUILD CONCLUIDO COM SUCESSO!
    echo ========================================================
    echo.
    echo   Arquivo: dist\ElysiusWhitelist.exe
    explorer dist
) else (
    echo.
    echo [ERRO] Build falhou!
)

pause
