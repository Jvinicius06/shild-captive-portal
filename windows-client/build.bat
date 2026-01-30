@echo off
chcp 65001 >nul
echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║     Elysius Whitelist Client - Build Script            ║
echo ║     Cria um .exe PORTAVEL (nao precisa Python)         ║
echo ╚════════════════════════════════════════════════════════╝
echo.

REM Verificar se Python está instalado (só precisa na máquina de BUILD)
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo        Instale Python 3.10+ em: https://www.python.org/downloads/
    echo        Marque "Add Python to PATH" durante instalacao
    pause
    exit /b 1
)

echo [OK] Python encontrado
python --version

REM Criar ambiente virtual se não existir
if not exist "venv" (
    echo.
    echo [INFO] Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual
        pause
        exit /b 1
    )
)

REM Ativar ambiente virtual
echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat

REM Atualizar pip
echo [INFO] Atualizando pip...
python -m pip install --upgrade pip >nul 2>&1

REM Instalar dependências
echo [INFO] Instalando dependencias...
pip install --upgrade pystray Pillow requests pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias
    pause
    exit /b 1
)

echo [OK] Dependencias instaladas

REM Criar ícone se não existir
if not exist "icon.ico" (
    echo [INFO] Criando icone...
    python create_icon.py 2>nul
    if not exist "icon.ico" (
        REM Fallback: criar ícone simples
        python -c "from PIL import Image,ImageDraw;img=Image.new('RGBA',(256,256),(0,0,0,0));d=ImageDraw.Draw(img);d.ellipse([16,16,240,240],fill='#1e3a8a',outline='#fbbf24',width=12);img.save('icon.ico')"
    )
)

REM Limpar builds anteriores
if exist "build" rmdir /s /q build >nul 2>&1
if exist "dist" rmdir /s /q dist >nul 2>&1
if exist "ElysiusWhitelist.spec" del /f /q ElysiusWhitelist.spec >nul 2>&1

echo.
echo [INFO] Compilando executavel...
echo        Isso pode levar alguns minutos...
echo.

REM Build com PyInstaller
REM --onefile     = Tudo em um único .exe
REM --noconsole   = Sem janela de console (só system tray)
REM --clean       = Limpa cache do PyInstaller
REM --hidden-import = Importações que o PyInstaller não detecta automaticamente

pyinstaller ^
    --onefile ^
    --noconsole ^
    --clean ^
    --name "ElysiusWhitelist" ^
    --icon "icon.ico" ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    --add-data "icon.ico;." ^
    --version-file version_info.txt ^
    whitelist_client.py 2>build_errors.log

if not exist "dist\ElysiusWhitelist.exe" (
    echo.
    echo [ERRO] Build falhou!
    echo        Verifique o arquivo build_errors.log
    echo.
    type build_errors.log
    pause
    exit /b 1
)

REM Mostrar tamanho do arquivo
for %%A in ("dist\ElysiusWhitelist.exe") do set SIZE=%%~zA
set /a SIZE_MB=%SIZE%/1048576

echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║              BUILD CONCLUIDO COM SUCESSO!              ║
echo ╚════════════════════════════════════════════════════════╝
echo.
echo   Arquivo: dist\ElysiusWhitelist.exe
echo   Tamanho: ~%SIZE_MB% MB
echo.
echo   ┌─────────────────────────────────────────────────────┐
echo   │  Este .exe eh 100%% PORTAVEL                        │
echo   │  NAO precisa instalar Python no PC do usuario      │
echo   │  Basta copiar e executar!                          │
echo   └─────────────────────────────────────────────────────┘
echo.
echo   Para distribuir:
echo   1. Copie dist\ElysiusWhitelist.exe
echo   2. Envie para os usuarios
echo   3. Eles executam e pronto!
echo.

REM Limpar arquivos temporários
del /f /q build_errors.log >nul 2>&1

REM Abrir pasta com o executável
explorer dist

pause
