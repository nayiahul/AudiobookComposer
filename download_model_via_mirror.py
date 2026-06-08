#!/usr/bin/env python3
"""使用国内镜像源下载Whisper模型的脚本"""

import os
import sys
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from huggingface_hub import snapshot_download
    print("✓ 成功导入 huggingface_hub")

    # 设置国内镜像源
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
    print("ℹ 已设置国内镜像源: https://hf-mirror.com")

    # 设置模型保存路径
    model_dir = Path.home() / ".cache" / "whisper"
    model_dir.mkdir(parents=True, exist_ok=True)
    print(f"ℹ 模型将保存到: {model_dir}")

    print("ℹ 开始从国内镜像源下载 Base 模型...")
    print("ℹ 请耐心等待，这可能需要几分钟时间...")

    # 从国内镜像源下载Base模型
    model_path = snapshot_download(
        repo_id="Systran/faster-whisper-base",
        local_dir=str(model_dir / "base"),
        local_dir_use_symlinks=False,
        resume_download=True
    )

    print("✓ Base 模型下载完成!")
    print(f"ℹ 模型保存路径: {model_path}")

    # 验证模型文件
    model_files = list(Path(model_path).rglob("*"))
    if model_files:
        print("ℹ 模型目录中的文件:")
        for f in model_files:
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  - {f.name} ({size_mb:.2f} MB)")
    else:
        print("⚠ 模型目录为空")

except Exception as e:
    print(f"✗ 下载过程中出现错误: {e}")
    import traceback
    traceback.print_exc()