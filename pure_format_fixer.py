#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕格式修复器 - 只修复格式，不修改时间值
确保毫秒位数正确，但保持原始时间不变
"""

import re
from typing import Dict, List, Tuple

class PureFormatFixer:
    """纯粹的格式修复器 - 只修复毫秒位数，不修改时间值"""
    
    def __init__(self):
        # 匹配各种时间轴格式
        self.timestamp_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d+)\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d+)')
    
    def fix_millisecond_format(self, time_str: str, ms_str: str) -> str:
        """
        修复毫秒格式，保持时间值不变
        
        Args:
            time_str: 时间部分 (HH:MM:SS)
            ms_str: 原始毫秒字符串
            
        Returns:
            修复后的完整时间字符串
        """
        ms_len = len(ms_str)
        
        if ms_len == 3:
            # 已经是标准格式
            return f"{time_str},{ms_str}"
        elif ms_len < 3:
            # 毫秒位数不足，补零
            fixed_ms = ms_str.ljust(3, '0')
            return f"{time_str},{fixed_ms}"
        else:  # ms_len > 3
            # 毫秒位数过多，截断但不进位
            # 保持原始值不变，只是截断多余位数
            fixed_ms = ms_str[:3]
            return f"{time_str},{fixed_ms}"
    
    def fix_timestamp_line(self, line: str) -> str:
        """
        修复时间轴行，只修复格式不修改时间值
        
        Args:
            line: 原始时间轴行
            
        Returns:
            修复后的时间轴行
        """
        match = self.timestamp_pattern.search(line)
        if not match:
            return line
        
        # 提取各个部分
        start_h, start_m, start_s, start_ms = match.group(1), match.group(2), match.group(3), match.group(4)
        end_h, end_m, end_s, end_ms = match.group(5), match.group(6), match.group(7), match.group(8)
        
        # 构建时间字符串
        start_time = f"{start_h}:{start_m}:{start_s}"
        end_time = f"{end_h}:{end_m}:{end_s}"
        
        # 修复毫秒格式
        fixed_start = self.fix_millisecond_format(start_time, start_ms)
        fixed_end = self.fix_millisecond_format(end_time, end_ms)
        
        # 替换原行中的时间轴
        original_timestamp = f"{start_h}:{start_m}:{start_s},{start_ms} --> {end_h}:{end_m}:{end_s},{end_ms}"
        fixed_timestamp = f"{fixed_start} --> {fixed_end}"
        
        return line.replace(original_timestamp, fixed_timestamp)
    
    def validate_and_fix_subtitle(self, subtitle_content: str) -> Dict[str, any]:
        """
        验证并修复字幕格式
        
        Args:
            subtitle_content: 字幕内容
            
        Returns:
            修复结果
        """
        lines = subtitle_content.split('\n')
        fixed_lines = []
        changes = []
        
        for i, line in enumerate(lines, 1):
            if '-->' in line:
                # 检查是否需要修复
                match = self.timestamp_pattern.search(line)
                if match:
                    start_ms = match.group(4)
                    end_ms = match.group(8)
                    
                    # 检查毫秒位数
                    if len(start_ms) != 3 or len(end_ms) != 3:
                        # 需要修复
                        fixed_line = self.fix_timestamp_line(line)
                        if fixed_line != line:
                            changes.append({
                                'line_number': i,
                                'original': line.strip(),
                                'fixed': fixed_line.strip(),
                                'start_ms_original': start_ms,
                                'start_ms_fixed': match.group(4) if len(start_ms) == 3 else start_ms[:3] if len(start_ms) > 3 else start_ms.ljust(3, '0'),
                                'end_ms_original': end_ms,
                                'end_ms_fixed': match.group(8) if len(end_ms) == 3 else end_ms[:3] if len(end_ms) > 3 else end_ms.ljust(3, '0')
                            })
                        fixed_lines.append(fixed_line)
                    else:
                        # 已经是标准格式
                        fixed_lines.append(line)
                else:
                    # 不匹配时间轴格式，保持原样
                    fixed_lines.append(line)
            else:
                # 非时间轴行，保持原样
                fixed_lines.append(line)
        
        return {
            'original_content': subtitle_content,
            'fixed_content': '\n'.join(fixed_lines),
            'changes': changes,
            'total_changes': len(changes),
            'needs_fix': len(changes) > 0
        }


def test_pure_format_fixer():
    """测试纯粹的格式修复器"""
    fixer = PureFormatFixer()
    
    print("=== 纯粹格式修复器测试 ===\n")
    
    # 测试案例1：毫秒位数过多
    test1 = """1
00:00:00,000 --> 00:00:08,8000
这是第一条字幕

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕"""
    
    print("测试1: 毫秒位数过多 (8000 → 800)")
    result1 = fixer.validate_and_fix_subtitle(test1)
    if result1['needs_fix']:
        change = result1['changes'][0]
        print(f"第 {change['line_number']} 行:")
        print(f"  修复前: {change['original']}")
        print(f"  修复后: {change['fixed']}")
        print(f"  开始毫秒: {change['start_ms_original']} → {change['start_ms_fixed']}")
        print(f"  结束毫秒: {change['end_ms_original']} → {change['end_ms_fixed']}")
    else:
        print("无需修复")
    print()
    
    # 测试案例2：毫秒位数不足
    test2 = """1
00:00:00,00 --> 00:00:08,8
这是第一条字幕"""
    
    print("测试2: 毫秒位数不足 (00 → 000, 8 → 800)")
    result2 = fixer.validate_and_fix_subtitle(test2)
    if result2['needs_fix']:
        change = result2['changes'][0]
        print(f"第 {change['line_number']} 行:")
        print(f"  修复前: {change['original']}")
        print(f"  修复后: {change['fixed']}")
        print(f"  开始毫秒: {change['start_ms_original']} → {change['start_ms_fixed']}")
        print(f"  结束毫秒: {change['end_ms_original']} → {change['end_ms_fixed']}")
    else:
        print("无需修复")
    print()
    
    # 测试案例3：已经是标准格式
    test3 = """1
00:00:00,000 --> 00:00:08,800
这是第一条字幕"""
    
    print("测试3: 已经是标准格式")
    result3 = fixer.validate_and_fix_subtitle(test3)
    print(f"需要修复: {result3['needs_fix']}")
    if not result3['needs_fix']:
        print("✅ 正确识别为标准格式，无需修改")
    print()

if __name__ == "__main__":
    test_pure_format_fixer()