import os

DEFAULT_SETTINGS = {
    'BOOKS_ROOT': '电子书',
    'DEFAULT_BOOK': '红楼梦',
    'CONFIG_DIR_NAME': '配置信息',
    'DEEPSEEK_API_KEY': os.environ.get('DEEPSEEK_API_KEY', '')
}

# Whisper模型配置信息
WHISPER_MODELS = {
    'tiny': {
        'file_patterns': ['tiny.pt', 'ggml-tiny.bin', 'ggml-tiny-q8_0.bin', 'model.bin'],
        'parameters': '39M',
        'speed': '非常快',
        'accuracy': '低',
        'description': '最快但精度最低的模型，适合快速测试或实时应用',
        'recommended_use': '快速测试、实时转录、低资源设备',
        'languages': '支持99种语言，英文效果最佳',
        'vram_requirement': '1GB',
        'performance_factor': '32倍快于large模型'
    },
    'base': {
        'file_patterns': ['base.pt', 'ggml-base.bin', 'ggml-base-q8_0.bin', 'model.bin'],
        'parameters': '74M',
        'speed': '快',
        'accuracy': '中等',
        'description': '速度和精度的平衡选择，适合日常使用',
        'recommended_use': '日常使用、平衡性能与精度',
        'languages': '支持99种语言，中英文效果良好',
        'vram_requirement': '1GB',
        'performance_factor': '16倍快于large模型'
    },
    'small': {
        'file_patterns': ['small.pt', 'ggml-small.bin', 'ggml-small-q8_0.bin', 'model.bin'],
        'parameters': '244M',
        'speed': '中等',
        'accuracy': '高',
        'description': '高精度模型，适合对质量要求较高的应用',
        'recommended_use': '高质量转录、专业应用',
        'languages': '支持99种语言，中文效果优秀',
        'vram_requirement': '2GB',
        'performance_factor': '6倍快于large模型'
    },
    'medium': {
        'file_patterns': ['medium.pt', 'ggml-medium.bin', 'ggml-medium-q8_0.bin', 'model.bin'],
        'parameters': '769M',
        'speed': '慢',
        'accuracy': '很高',
        'description': '非常高精度的模型，适合专业级应用',
        'recommended_use': '专业级转录、高质量内容制作',
        'languages': '支持99种语言，多语言混合识别优秀',
        'vram_requirement': '5GB',
        'performance_factor': '2倍快于large模型'
    },
    'large': {
        'file_patterns': ['large.pt', 'ggml-large.bin', 'ggml-large-q8_0.bin', 'ggml-large-v3.bin', 'ggml-large-v3-turbo-q8_0.bin', 'model.bin'],
        'parameters': '1550M',
        'speed': '非常慢',
        'accuracy': '最高',
        'description': '最高精度的模型，适合对准确性要求极高的场景',
        'recommended_use': '最高精度要求、学术研究、重要内容转录',
        'languages': '支持99种语言，最准确的多语言识别',
        'vram_requirement': '10GB',
        'performance_factor': '基准速度'
    },
    'large-v3-turbo': {
        'file_patterns': ['ggml-large-v3-turbo-q8_0.bin', 'model.bin'],
        'parameters': '1550M',
        'speed': '中等',
        'accuracy': '很高',
        'description': 'Large-v3的优化版本，在保持高精度的同时大幅提升速度',
        'recommended_use': '高精度与速度平衡的最佳选择',
        'languages': '支持99种语言，接近large模型的精度',
        'vram_requirement': '6GB',
        'performance_factor': '8倍快于large模型'
    }
}