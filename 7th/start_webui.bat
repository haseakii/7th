@echo off
chcp 65001 > /dev/null
cd /d "%~dp0"
echo 正在启动 E7 Shop Bot WebUI...
echo 浏览器打开后请稍等（首次加载OCR模型约需数秒）
echo.
start http://localhost:8080
"C:\Users\18579\AppData\Local\Python\pythoncore-3.14-64\python.exe" gui.py --host 0.0.0.0 --port 8080
pause
