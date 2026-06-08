#!/usr/bin/env python3
"""测试当前模型文件是否能正确加载Base模型（使用直接路径）"""

import sys
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from faster_whisper import WhisperModel
    print("✓ 成功导入 faster-whisper")

    # 直接使用模型文件所在的目录路径
    model_path = Path.home() / ".cache" / "whisper"
    print(f"ℹ 使用模型目录: {model_path}")

    if model_path.exists():
        print(f"✓ 模型目录存在")
        # 列出目录中的文件
        model_files = list(model_path.iterdir())
        print("ℹ 目录中的文件:")
        for f in model_files:
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  - {f.name} ({size_mb:.2f} MB)")
    else:
        print(f"✗ 模型目录不存在: {model_path}")
        sys.exit(1)

    print("ℹ 开始加载 Base 模型...")
    print("ℹ 这可能需要一些时间，请耐心等待...")

    # 使用目录路径直接加载模型，而不是使用模型名称
    model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
    print("✓ Base 模型加载成功!")

    print("✓ 模型测试完成!")

except Exception as e:
    print(f"✗ 加载过程中出现错误: {e}")
    import traceback
    traceback.print_exc()