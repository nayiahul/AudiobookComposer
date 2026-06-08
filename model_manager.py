#!/usr/bin/env python3
"""
模型管理工具
用于检测、下载和管理Whisper模型
"""

import os
import sys
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def check_model_exists(model_size):
    """
    准确判断本地模型是否存在

    Args:
        model_size: 模型大小 (tiny, base, small, medium, large, large-v3-turbo)

    Returns:
        bool: 模型是否存在
    """
    model_file_map = {
        "tiny": "~/.cache/whisper/models/tiny/ggml-tiny.bin",
        "base": "~/.cache/whisper/models/base/ggml-base.bin",
        "small": "~/.cache/whisper/models/small/ggml-small.bin",
        "medium": "~/.cache/whisper/models/medium/ggml-medium.bin",
        "large": "~/.cache/whisper/models/large/ggml-large.bin",
        "large-v3-turbo": "~/.cache/whisper/models/large-v3-turbo/ggml-large-v3-turbo.bin"
    }

    if model_size not in model_file_map:
        raise ValueError(f"不支持的模型大小: {model_size}")

    model_path = os.path.expanduser(model_file_map[model_size])
    exists = os.path.exists(model_path) and os.path.getsize(model_path) > 0
    print(f"检查模型 {model_size}: {'存在' if exists else '不存在'} - {model_path}")
    return exists

def get_model_path(model_size):
    """
    获取模型路径

    Args:
        model_size: 模型大小

    Returns:
        模型目录路径
    """
    if not check_model_exists(model_size):
        raise FileNotFoundError(f"模型 {model_size} 不存在")

    model_file_map = {
        "tiny": "~/.cache/whisper/models/tiny/ggml-tiny.bin",
        "base": "~/.cache/whisper/models/base/ggml-base.bin",
        "small": "~/.cache/whisper/models/small/ggml-small.bin",
        "medium": "~/.cache/whisper/models/medium/ggml-medium.bin",
        "large": "~/.cache/whisper/models/large/ggml-large.bin",
        "large-v3-turbo": "~/.cache/whisper/models/large-v3-turbo/ggml-large-v3-turbo.bin"
    }

    model_path = os.path.expanduser(model_file_map[model_size])
    return os.path.dirname(model_path)

def download_model(model_size):
    """
    下载指定大小的模型

    Args:
        model_size: 模型大小
    """
    try:
        # 导入必要的模块
        import os
        from huggingface_hub import snapshot_download

        # 设置环境变量使用国内镜像
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

        model_repo_map = {
            "tiny": "Systran/faster-whisper-tiny",
            "base": "Systran/faster-whisper-base",
            "small": "Systran/faster-whisper-small",
            "medium": "Systran/faster-whisper-medium",
            "large": "Systran/faster-whisper-large-v3",
            "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo"
        }

        if model_size not in model_repo_map:
            raise ValueError(f"不支持的模型大小: {model_size}")

        repo_id = model_repo_map[model_size]
        model_dir = os.path.expanduser(f"~/.cache/whisper/models/{model_size}")

        # 确保目录存在
        os.makedirs(model_dir, exist_ok=True)

        print(f"开始下载 {model_size} 模型...")
        print(f"仓库: {repo_id}")
        print(f"保存到: {model_dir}")

        # 下载模型
        snapshot_download(
            repo_id=repo_id,
            local_dir=model_dir,
            local_dir_use_symlinks=False,
            resume_download=True
        )

        print(f"✓ {model_size} 模型下载完成!")

    except Exception as e:
        print(f"✗ 下载 {model_size} 模型时出现错误: {e}")
        raise

def check_and_download_model(model_size):
    """
    检查模型是否存在，如果不存在则下载

    Args:
        model_size: 模型大小

    Returns:
        模型目录路径
    """
    if not check_model_exists(model_size):
        print(f"模型 {model_size} 不存在，开始下载...")
        download_model(model_size)
        print(f"模型 {model_size} 下载完成")

    return get_model_path(model_size)

def list_available_models():
    """
    列出所有可用的模型
    """
    model_sizes = ["tiny", "base", "small", "medium", "large", "large-v3-turbo"]
    available_models = []

    print("检查本地模型:")
    for model_size in model_sizes:
        if check_model_exists(model_size):
            model_path = os.path.expanduser(f"~/.cache/whisper/models/{model_size}/ggml-{model_size}.bin")
            size_mb = os.path.getsize(model_path) / (1024 * 1024)
            print(f"  ✓ {model_size.upper()}: {size_mb:.1f} MB")
            available_models.append(model_size)
        else:
            print(f"  ✗ {model_size.upper()}: 未安装")

    return available_models

if __name__ == "__main__":
    available_models = list_available_models()
    print(f"\n总共找到 {len(available_models)} 个模型: {', '.join([m.upper() for m in available_models])}")