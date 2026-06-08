#!/usr/bin/env python3
"""重新下载Base模型"""

import os
import sys
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    print("ℹ 开始下载Base模型...")

    # 设置环境变量使用国内镜像
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

    from huggingface_hub import snapshot_download

    # 下载Base模型到指定目录
    model_path = snapshot_download(
        repo_id="Systran/faster-whisper-base",
        local_dir="/Users/nayiahlu/.cache/whisper",
        local_dir_use_symlinks=False,
        resume_download=True
    )

    print(f"✓ Base模型下载完成，保存到: {model_path}")

    # 验证文件
    model_bin = Path("/Users/nayiahlu/.cache/whisper/model.bin")
    if model_bin.exists():
        size_mb = model_bin.stat().st_size / (1024 * 1024)
        print(f"✓ model.bin文件存在，大小: {size_mb:.2f} MB")
    else:
        print("✗ model.bin文件不存在")

except Exception as e:
    print(f"✗ 下载过程中出现错误: {e}")
    import traceback
    traceback.print_exc()