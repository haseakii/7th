@echo off
echo ========================================
echo   ShopBot 打包脚本
echo ========================================
echo.

:: 检查 pyinstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install pyinstaller
)

echo 开始打包...
pyinstaller build.spec --noconfirm

echo.
if exist "dist\ShopBot\ShopBot.exe" (
    echo ✅ 打包成功！
    echo 输出目录: dist\ShopBot\
    echo 可执行文件: dist\ShopBot\ShopBot.exe
    echo.
    echo 使用方法:
    echo   dist\ShopBot\ShopBot.exe              无 UI 模式
    echo   dist\ShopBot\ShopBot.exe --webui      带 Web UI
) else (
    echo ❌ 打包失败，请检查错误信息
)
pause
