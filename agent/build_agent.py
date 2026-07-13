# Build Windows Agent .exe
# 將 agent.py 打包成一個 exe 檔案，用戶下載就用到
#
# 用法：python build_agent.py

import os
import sys

# Check PyInstaller
try:
    import PyInstaller
except ImportError:
    print("❌ 請先安裝 PyInstaller：pip install pyinstaller")
    sys.exit(1)

output_dir = os.path.join(os.path.dirname(__file__), "dist")

print("=" * 56)
print("  📦 Building MT5 Cloud Agent.exe")
print("=" * 56)
print()

os.system(f'pyinstaller --onefile --windowed --name "MT5 Cloud Agent" '
          f'--add-data "agent.py;." '
          f'--distpath "{output_dir}" agent.py')

print()
print(f"✅ 完成！檔案位置：{output_dir}/MT5 Cloud Agent.exe")
print()
