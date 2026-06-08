#!/usr/bin/env python3
"""测试Whisper模型下载的脚本"""

import os
import sys
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from faster_whisper import WhisperModel
    print("✓ 成功导入 faster-whisper")

    # 设置模型保存路径
    model_dir = Path.home() / ".cache" / "whisper"
    model_dir.mkdir(parents=True, exist_ok=True)
    print(f"ℹ 模型将保存到: {model_dir}")

    print("ℹ 开始下载 Base 模型...")
    print("ℹ 请耐心等待，这可能需要几分钟时间...")

    # 下载Base模型，显式设置local_files_only=False
    model = WhisperModel("base", device="cpu", compute_type="int8", local_files_only=False)
    print("✓ Base 模型下载完成!")

    # 验证模型文件
    expected_model_file = model_dir / "base.pt"
    if expected_model_file.exists():
        size_mb = expected_model_file.stat().st_size / (1024 * 1024)
        print(f"✓ 模型文件已验证: {expected_model_file}")
        print(f"ℹ 文件大小: {size_mb:.2f} MB")
    else:
        print("⚠ 未找到预期的模型文件，但模型对象已创建")

except Exception as e:
    print(f"✗ 下载过程中出现错误: {e}")
    import traceback
    traceback.print_exc()