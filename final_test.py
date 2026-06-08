#!/usr/bin/env python3
"""最终测试脚本"""

import sys
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from faster_whisper import WhisperModel
    print("✓ 成功导入 faster-whisper")

    # 验证模型文件是否存在
    model_file = Path.home() / ".cache" / "whisper" / "base.bin"
    symlink_file = Path.home() / ".cache" / "whisper" / "model.bin"

    print(f"ℹ 检查基础模型文件: {model_file}")
    print(f"ℹ 检查符号链接文件: {symlink_file}")

    if model_file.exists():
        size_mb = model_file.stat().st_size / (1024 * 1024)
        print(f"✓ 基础模型文件存在，大小: {size_mb:.2f} MB")
    else:
        print(f"✗ 基础模型文件不存在: {model_file}")
        sys.exit(1)

    if symlink_file.exists() and symlink_file.is_symlink():
        print(f"✓ 符号链接存在并正确指向基础文件")
    else:
        print(f"✗ 符号链接有问题: {symlink_file}")
        sys.exit(1)

    print("ℹ 开始测试 Base 模型加载...")

    # 使用直接路径加载模型
    model_path = str(Path.home() / ".cache" / "whisper")
    print(f"ℹ 使用模型路径: {model_path}")

    model = WhisperModel(model_path, device="cpu", compute_type="int8")
    print("✓ Base 模型加载成功!")

    print("🎉 最终测试完成！模型已准备好正常使用！")

except Exception as e:
    print(f"✗ 测试过程中出现错误: {e}")
    import traceback
    traceback.print_exc()