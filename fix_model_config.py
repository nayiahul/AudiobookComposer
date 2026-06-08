#!/usr/bin/env python3
"""修复模型配置的脚本"""

import json
from pathlib import Path

# 创建模型配置文件
config = {
    "models": {
        "tiny": {
            "path": "~/.cache/whisper/tiny",
            "installed": False,
            "size_mb": 0
        },
        "base": {
            "path": "~/.cache/whisper/base",
            "installed": True,
            "size_mb": 138.5
        },
        "small": {
            "path": "~/.cache/whisper/small",
            "installed": False,
            "size_mb": 0
        },
        "medium": {
            "path": "~/.cache/whisper/medium",
            "installed": False,
            "size_mb": 0
        },
        "large": {
            "path": "~/.cache/whisper/large",
            "installed": False,
            "size_mb": 0
        },
        "large-v3-turbo": {
            "path": "~/.cache/whisper/large-v3-turbo",
            "installed": False,
            "size_mb": 0
        }
    }
}

# 保存配置文件
config_path = Path("model_config.json")
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"✓ 模型配置文件已创建: {config_path}")

# 显示配置内容
print("\n配置内容:")
print(json.dumps(config, indent=2, ensure_ascii=False))