#!/usr/bin/env python3
"""
修正的时间轴修改模式分析
正确解析SRT时间格式
"""

import re

def analyze_timecode_patterns_fixed(original_subtitle, corrected_subtitle):
    """分析时间轴修改的模式"""
    
    # 提取字幕条目
    entry_pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?(?=\n\d+\n|\Z))'
    
    original_entries = re.findall(entry_pattern, original_subtitle, re.DOTALL)
    corrected_entries = re.findall(entry_pattern, corrected_subtitle, re.DOTALL)
    
    def time_to_ms(time_str):
        """将SRT时间字符串转换为毫秒"""
        # SRT格式：00:00:08,800
        parts = time_str.split(':')
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_ms = parts[2].split(',')
            if len(seconds_ms) == 2:
                seconds = int(seconds_ms[0])
                milliseconds = int(seconds_ms[1])
                return hours * 3600 * 1000 + minutes * 60 * 1000 + seconds * 1000 + milliseconds
        return 0
    
    print("时间轴修改模式分析 (修正版):")
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
            print(f"  原始时间: {orig_start} --> {orig_end}")
            print(f"  校正时间: {corr_start} --> {corr_end}")
            print(f"  持续时间: {orig_duration}ms → {corr_duration}ms")
            
            # 检测异常
            is_suspicious = False
            suspicion_reasons = []
            
            if duration_change_ratio > 1.2 or duration_change_ratio < 0.8:  # 持续时间变化超过20%
                is_suspicious = True
                suspicion_reasons.append(f"持续时间变化{duration_change_ratio:.1f}倍")
            
            if start_time_change > 500:  # 开始时间变化超过500ms
                is_suspicious = True
                suspicion_reasons.append(f"开始时间偏移{start_time_change}ms")
            
            if end_time_change > 500:  # 结束时间变化超过500ms
                is_suspicious = True
                suspicion_reasons.append(f"结束时间偏移{end_time_change}ms")
            
            if is_suspicious:
                suspicious_changes.append({
                    'entry': orig_num,
                    'reasons': suspicion_reasons,
                    'orig_duration': orig_duration,
                    'corr_duration': corr_duration,
                    'duration_ratio': duration_change_ratio,
                    'start_change': start_time_change,
                    'end_change': end_time_change
                })
                print(f"  ⚠️ 异常修改: {'; '.join(suspicion_reasons)}")
            else:
                print(f"  ✓ 正常范围")
    
    print("\n" + "=" * 60)
    if suspicious_changes:
        print(f"发现 {len(suspicious_changes)} 处异常时间轴修改:")
        for change in suspicious_changes:
            print(f"  第 {change['entry']} 条: {'; '.join(change['reasons'])}")
            print(f"    持续时间: {change['orig_duration']}ms → {change['corr_duration']}ms")
            print(f"    变化比例: {change['duration_ratio']:.2f}x")
    else:
        print("未发现异常时间轴修改")
    
    return suspicious_changes

# 测试用户提供的真实案例
original = """1
00:00:00,000 --> 00:00:08,800
这是第一条字幕内容

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕内容"""

corrected = """1
00:00:00,000 --> 00:00:16,000
这是第一条字幕内容（已校正）

2
00:00:16,000 --> 00:00:30,440
这是第二条字幕内容（已校正）"""

suspicious = analyze_timecode_patterns_fixed(original, corrected)
print(f"\n总共发现 {len(suspicious)} 处可疑修改")