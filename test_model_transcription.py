#!/usr/bin/env python3
"""测试Whisper模型转录功能的脚本"""

import os
import sys
from pathlib import Path
import tempfile
import numpy as np

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from faster_whisper import WhisperModel
    print("✓ 成功导入 faster-whisper")

    # 设置模型路径
    model_path = Path.home() / ".cache" / "whisper" / "base"
    print(f"ℹ 模型路径: {model_path}")

    print("ℹ 开始加载 Base 模型...")

    # 加载模型
    model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
    print("✓ Base 模型加载成功!")

    # 创建一个简短的测试音频（这里我们创建一个简单的正弦波作为示例）
    print("ℹ 创建测试音频...")

    # 生成1秒钟的440Hz正弦波（模拟音频）
    sample_rate = 16000
    duration = 1.0  # 1秒
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * 440 * t)  # 440Hz正弦波

    # 保存为临时WAV文件
    import soundfile as sf
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        sf.write(tmp_file.name, audio_data, sample_rate)
        temp_audio_path = tmp_file.name

    print(f"✓ 测试音频已创建: {temp_audio_path}")

    print("ℹ 开始转录测试音频...")

    # 转录音频（这里只是测试模型能否正常工作）
    segments, info = model.transcribe(temp_audio_path, beam_size=5)

    print("✓ 音频转录测试成功!")
    print(f"  检测到的语言: {info.language}")
    print(f"  语言概率: {info.language_probability:.2f}")
    print(f"  音频时长: {info.duration_after_vad:.2f} 秒")

    # 清理临时文件
    os.unlink(temp_audio_path)
    print("✓ 临时文件已清理")

    print("✓ 模型功能测试完成，一切正常!")

except Exception as e:
    print(f"✗ 测试过程中出现错误: {e}")
    import traceback
    traceback.print_exc()

    # 清理临时文件（如果存在）
    try:
        if 'temp_audio_path' in locals():
            os.unlink(temp_audio_path)
    except:
        pass