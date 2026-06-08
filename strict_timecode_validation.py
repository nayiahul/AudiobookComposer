#!/usr/bin/env python3
"""
严格的时间轴保护机制
拒绝接受异常的时间轴修改
"""

import re
import logging

logger = logging.getLogger(__name__)

def strict_timecode_validation(original_subtitle: str, corrected_subtitle: str, 
                               max_duration_change: float = 0.1,  # 最大持续时间变化10%
                               max_time_offset: int = 100) -> dict:  # 最大时间偏移100ms
    """
    严格的时间轴验证 - 拒绝异常修改
    
    Args:
        original_subtitle: 原始字幕文本
        corrected_subtitle: 校正后的字幕文本
        max_duration_change: 允许的最大持续时间变化比例（默认10%）
        max_time_offset: 允许的最大时间偏移（默认100ms）
        
    Returns:
        验证结果字典，包含是否拒绝的建议
    """
    
    # 提取字幕条目
    entry_pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?(?=\n\d+\n|\Z))'
    
    original_entries = re.findall(entry_pattern, original_subtitle, re.DOTALL)
    corrected_entries = re.findall(entry_pattern, corrected_subtitle, re.DOTALL)
    
    def time_to_ms(time_str):
        """将SRT时间字符串转换为毫秒"""
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
    
    print("严格时间轴验证:")
    print("=" * 60)
    
    rejected_changes = []
    acceptable_changes = []
    
    for i, (orig_num, orig_start, orig_end, orig_text) in enumerate(original_entries):
        if i >= len(corrected_entries):
            break
            
        corr_num, corr_start, corr_end, corr_text = corrected_entries[i]
        
        # 转换为毫秒
        orig_start_ms = time_to_ms(orig_start)
        orig_end_ms = time_to_ms(orig_end)
        corr_start_ms = time_to_ms(corr_start)
        corr_end_ms = time_to_ms(corr_end)
        
        orig_duration = orig_end_ms - orig_start_ms
        corr_duration = corr_end_ms - corr_start_ms
        
        # 计算变化
        duration_change_ratio = abs(corr_duration - orig_duration) / orig_duration if orig_duration > 0 else 0
        start_time_offset = abs(corr_start_ms - orig_start_ms)
        end_time_offset = abs(corr_end_ms - orig_end_ms)
        
        print(f"\n第 {orig_num} 条字幕:")
        print(f"  原始: {orig_start} --> {orig_end} (持续: {orig_duration}ms)")
        print(f"  校正: {corr_start} --> {corr_end} (持续: {corr_duration}ms)")
        
        # 检查是否超出允许范围
        is_rejected = False
        rejection_reasons = []
        
        if duration_change_ratio > max_duration_change:
            is_rejected = True
            rejection_reasons.append(f"持续时间变化{duration_change_ratio*100:.1f}% (超过{max_duration_change*100}%)")
        
        if start_time_offset > max_time_offset:
            is_rejected = True
            rejection_reasons.append(f"开始时间偏移{start_time_offset}ms (超过{max_time_offset}ms)")
            
        if end_time_offset > max_time_offset:
            is_rejected = True
            rejection_reasons.append(f"结束时间偏移{end_time_offset}ms (超过{max_time_offset}ms)")
        
        if is_rejected:
            rejected_changes.append({
                'entry': orig_num,
                'reasons': rejection_reasons,
                'orig_duration': orig_duration,
                'corr_duration': corr_duration,
                'duration_change': duration_change_ratio,
                'start_offset': start_time_offset,
                'end_offset': end_time_offset
            })
            print(f"  ❌ 拒绝: {'; '.join(rejection_reasons)}")
        else:
            acceptable_changes.append({
                'entry': orig_num,
                'duration_change': duration_change_ratio,
                'start_offset': start_time_offset,
                'end_offset': end_time_offset
            })
            print(f"  ✓ 接受: 在允许范围内")
    
    print("\n" + "=" * 60)
    
    # 决策建议
    should_reject = len(rejected_changes) > 0
    
    if should_reject:
        print(f"建议: ❌ 拒绝整个校正结果")
        print(f"原因: {len(rejected_changes)} 处时间轴修改超出允许范围")
        for change in rejected_changes:
            print(f"  第 {change['entry']} 条: {'; '.join(change['reasons'])}")
    else:
        print(f"建议: ✓ 接受校正结果")
        if acceptable_changes:
            print(f"时间轴变化都在允许范围内:")
            for change in acceptable_changes:
                print(f"  第 {change['entry']} 条: 持续时间变化{change['duration_change']*100:.1f}%, 时间偏移{max(change['start_offset'], change['end_offset'])}ms")
    
    return {
        'should_reject': should_reject,
        'rejected_changes': rejected_changes,
        'acceptable_changes': acceptable_changes,
        'total_entries': len(original_entries),
        'rejected_count': len(rejected_changes),
        'acceptable_count': len(acceptable_changes)
    }

# 测试用户案例
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

result = strict_timecode_validation(original, corrected)
print(f"\n验证结果: {'拒绝' if result['should_reject'] else '接受'}")