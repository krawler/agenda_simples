@echo off
cls
echo Instalando dependencias...
pip install pyinstaller
echo.
echo Gerando executavel...
pyinstaller --onefile --name agenda --console agenda.py
echo.
echo Executavel gerado com sucesso!
echo Localizacao: dist\agenda.exe
pause
