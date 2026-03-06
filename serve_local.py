#!/usr/bin/env python3
"""
本地快速预览脚本
用法：python3 serve_local.py
访问：http://127.0.0.1:8008
文件变更后自动刷新，Ctrl+C 停止。
"""

import subprocess
import sys
import os
from pathlib import Path

REQUIREMENTS_FILE = Path(__file__).resolve().parent / "requirements.txt"

def install_requirements():
    if not REQUIREMENTS_FILE.exists():
        print(f"\n❌ 未找到依赖文件: {REQUIREMENTS_FILE}")
        sys.exit(1)

    print(f"⚙️  从 {REQUIREMENTS_FILE.name} 安装依赖（含版本约束）")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS_FILE)]
    )
    print("✅ 依赖安装完成\n")

def main():
    install_requirements()

    print("=" * 50)
    print("  本地预览服务器")
    print("=" * 50)
    print("🌐 地址: http://127.0.0.1:8008")
    print("🔄 文件保存后自动刷新")
    print("⛔ Ctrl+C 停止\n")

    try:
        env = os.environ.copy()
        # mkdocs-material 9.7.x prints this banner unconditionally; keep logs clean locally.
        env.setdefault("NO_MKDOCS_2_WARNING", "1")
        subprocess.run(
            ["mkdocs", "serve", "-a", "127.0.0.1:8008", "--open", "--watch-theme"],
            env=env,
            check=True,
        )
    except KeyboardInterrupt:
        print("\n\n✅ 预览服务器已停止")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
