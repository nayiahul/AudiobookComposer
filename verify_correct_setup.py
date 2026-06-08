#!/usr/bin/env python3
"""验证Base模型是否正常工作"""

import sys
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from faster_whisper import WhisperModel
    print("✓ 成功导入 faster-whisper")

    # 验证模型文件是否存在
    model_file = Path.home() / ".cache" / "whisper" / "ggml-base.bin"
    print(f"ℹ 检查模型文件: {model_file}")

    if model_file.exists():
        size_mb = model_file.stat().st_size / (1024 * 1024)
        print(f"✓ Base模型文件存在，大小: {size_mb:.2f} MB")
    else:
        print(f"✗ Base模型文件不存在: {model_file}")
        sys.exit(1)

    print("ℹ 开始测试 Base 模型加载...")

    # 使用直接路径加载模型（这是应用会使用的方式）
    model_path = str(Path.home() / ".cache" / "whisper")
    print(f"ℹ 使用模型路径: {model_path}")

    model = WhisperModel(model_path, device="cpu", compute_type="int8", local_files_only=True)
    print("✓ Base 模型加载成功!")

    print("🎉 模型已准备好正常使用！")

except Exception as e:
    print(f"✗ 测试过程中出现错误: {e}")
    import traceback
    traceback.print_exc()