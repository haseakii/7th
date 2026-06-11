"""
E7 Shop Bot 启动器 — 用于 PyInstaller 打包为 e7.exe

引导流程：
  1. 检测/创建 .venv 虚拟环境
  2. 安装 pip 依赖
  3. git clone/pull 更新代码
  4. 启动 WebUI
"""

import sys
import os


def main():
    # 确保工作目录在项目根目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        from deploy.installer import Installer

        inst = Installer()
        if not inst.venv_ready:
            print("首次运行，正在安装环境...")
            if not inst.install():
                print("安装失败，请查看日志")
                input("按 Enter 退出...")
                sys.exit(1)
            print("安装完成，正在启动...")
        else:
            # 检查更新
            try:
                if inst.config.AutoUpdate and inst.git.has_update():
                    print("检测到更新，正在更新...")
                    inst.update()
            except Exception:
                pass

        # 启动 WebUI
        inst.launch_gui()

    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按 Enter 退出...")


if __name__ == "__main__":
    main()
