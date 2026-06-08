#!/usr/bin/env python3
"""
分析时间轴修改模式
检测异常的时间轴变化
"""

import re
import math

def analyze_timecode_patterns(original_subtitle, corrected_subtitle):
    """分析时间轴修改的模式"""
    
    # 提取字幕条目
    entry_pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d+) --> (\d{2}:\d{2}:\d{2},\d+)\n(.*?(?=\n\d+\n|\Z))'
    
    original_entries = re.findall(entry_pattern, original_subtitle, re.DOTALL)
    corrected_entries = re.findall(entry_pattern, corrected_subtitle, re.DOTALL)
    
    def time_to_ms(time_str):
        """将时间字符串转换为毫秒"""
        # 处理格式：00:00:08,8000
        time_str = time_str.replace(',', ':')
        parts = time_str.split(':')
        if len(parts) == 4:
            hours, minutes, seconds, milliseconds = map(int, parts)
            return hours * 3600 * 1000 + minutes * 60 * 1000 + seconds * 1000 + milliseconds
        return 0
    
    def ms_to_time(ms):
        """将毫秒转换为时间字符串"""
        hours = ms // (3600 * 1000)
        ms %= (3600 * 1000)
        minutes = ms // (60 * 1000)
        ms %= (60 * 1000)
        seconds = ms // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    print("时间轴修改模式分析:")
    print("=" * 60)
    
    suspicious_changes = []
    
    for i, (orig_num, orig_start, orig_end, orig_text) in enumerate(original_entries):
        if i < len(corrected_entries):
            corr_num, corr_start, corr_end, corr_text = corrected_entries[i]
            
            # 转换为毫秒进行比较
            orig_start_ms = time_to_ms(orig_start)
            orig_end_ms = time_to_ms(orig_end)
            corr_start_ms = time_to_ms(corr_start)
            corr_end_ms = time_to_ms(corr_end)
            
            orig_duration = orig_end_ms - orig_start_ms
            corr_duration = corr_end_ms - corr_start_ms
            
            # 检查异常变化
            duration_change_ratio = corr_duration / orig_duration if orig_duration > 0 else 1
            start_time_change = abs(corr_start_ms - orig_start_ms)
            end_time_change = abs(corr_end_ms - orig_end_ms)
            
            print(f"\n第 {orig_num} 条字幕:")
            print(f"  原始时间: {orig_start} --> {orig_end} (持续: {orig_duration}ms)")
            print(f"  校正时间: {corr_start} --> {corr_end} (持续: {corr_duration}ms)")
            
            # 检测异常
            is_suspicious = False
            suspicion_reasons = []
            
            if duration_change_ratio > 1.5 or duration_change_ratio < 0.5:  # 持续时间变化超过50%
                is_suspicious = True
                suspicion_reasons.append(f"持续时间变化{duration_change_ratio:.1f}倍")
            
            if start_time_change > 1000:  # 开始时间变化超过1秒
                is_suspicious = True
                suspicion_reasons.append(f"开始时间偏移{start_time_change}ms")
            
            if end_time_change > 1000:  # 结束时间变化超过1秒
                is_suspicious = True
                suspicion_reasons.append(f"结束时间偏移{end_time_change}ms")
            
            if is_suspicious:
                suspicious_changes.append({
                    'entry': orig_num,
                    'reasons': suspicion_reasons,
                    'orig_duration': orig_duration,
                    'corr_duration': corr_duration,
                    'duration_ratio': duration_change_ratio
                })
                print(f"  ⚠️ 异常修改: {'; '.join(suspicion_reasons)}")
            else:
                print(f"  ✓ 正常范围")
    
    print("\n" + "=" * 60)
    if suspicious_changes:
        print(f"发现 {len(suspicious_changes)} 处异常时间轴修改:")
        for change in suspicious_changes:
            print(f"  第 {change['entry']} 条: {'; '.join(change['reasons'])}")
    else:
        print("未发现异常时间轴修改")
    
    return suspicious_changes

# 测试用户提供的案例
original = """1
00:00:00,000 --> 00:00:08,8000
这是第一条字幕内容

2
00:00:08,8000 --> 00:00:15,15440
这是第二条字幕内容"""

corrected = """1
00:00:00,000 --> 00:00:16,000
这是第一条字幕内容（已校正）

2
00:00:16,000 --> 00:00:30,440
这是第二条字幕内容（已校正）"""

suspicious = analyze_timecode_patterns(original, corrected)
print(f"\n总共发现 {len(suspicious)} 处可疑修改")