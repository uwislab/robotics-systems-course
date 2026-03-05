#!/usr/bin/env python3
"""
本地快速预览脚本
用法：python3 serve_local.py
访问：http://127.0.0.1:8008
文件变更后自动刷新，Ctrl+C 停止。
"""

import subprocess
import sys
import importlib.util

REQUIRED_PACKAGES = {
    "mkdocs": "mkdocs",
    "material": "mkdocs-material",
    "plantuml_markdown": "plantuml-markdown",
    "jieba": "jieba",
}

def check_and_install():
    missing = []
    for module, package in REQUIRED_PACKAGES.items():
        if importlib.util.find_spec(module) is None:
            missing.append(package)

    if missing:
        print(f"⚙️  安装缺少的依赖: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )
        print("✅ 依赖安装完成\n")

def main():
    check_and_install()

    print("=" * 50)
    print("  本地预览服务器")
    print("=" * 50)
    print("🌐 地址: http://127.0.0.1:8008")
    print("🔄 文件保存后自动刷新")
    print("⛔ Ctrl+C 停止\n")

    try:
        subprocess.run(
            ["mkdocs", "serve", "-a", "127.0.0.1:8008", "--open", "--watch-theme"],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n\n✅ 预览服务器已停止")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
