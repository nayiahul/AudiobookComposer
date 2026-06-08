#!/usr/bin/env python3
"""
字幕格式验证器 - 纯粹的格式校验，不涉及AI
确保字幕文件格式正确，能被视频生成器正确解析
"""

import re
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SubtitleFormatValidator:
    """字幕格式验证器 - 纯粹的格式检查"""
    
    def __init__(self):
        # SRT格式正则表达式
        self.time_pattern = r'^(\d{2}):(\d{2}):(\d{2}),(\d{3})$'
        self.timecode_pattern = r'^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$'
        self.entry_pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n(.*?(?=\n\d+\n|\Z))'
    
    def validate_time_format(self, time_str: str) -> bool:
        """验证时间格式是否正确"""
        match = re.match(self.time_pattern, time_str)
        if not match:
            return False
        
        hours, minutes, seconds, milliseconds = match.groups()
        
        # 检查数值范围
        hours_int = int(hours)
        minutes_int = int(minutes)
        seconds_int = int(seconds)
        milliseconds_int = int(milliseconds)
        
        return (0 <= hours_int <= 99 and 
                0 <= minutes_int <= 59 and 
                0 <= seconds_int <= 59 and 
                0 <= milliseconds_int <= 999)
    
    def validate_timecode_line(self, timecode_line: str) -> Dict[str, Any]:
        """验证时间轴行格式"""
        if not re.match(self.timecode_pattern, timecode_line.strip()):
            return {
                'valid': False,
                'error': '时间轴格式错误',
                'expected': 'HH:MM:SS,mmm --> HH:MM:SS,mmm',
                'actual': timecode_line.strip()
            }
        
        # 分离开始和结束时间
        try:
            start_time, end_time = timecode_line.strip().split(' --> ')
            
            if not self.validate_time_format(start_time):
                return {
                    'valid': False,
                    'error': f'开始时间格式错误: {start_time}',
                    'time_type': 'start'
                }
            
            if not self.validate_time_format(end_time):
                return {
                    'valid': False,
                    'error': f'结束时间格式错误: {end_time}',
                    'time_type': 'end'
                }
            
            # 检查时间逻辑（结束时间必须晚于开始时间）
            start_ms = self.time_to_ms(start_time)
            end_ms = self.time_to_ms(end_time)
            
            if end_ms <= start_ms:
                return {
                    'valid': False,
                    'error': '结束时间必须晚于开始时间',
                    'start_time': start_time,
                    'end_time': end_time,
                    'start_ms': start_ms,
                    'end_ms': end_ms
                }
            
            return {
                'valid': True,
                'start_time': start_time,
                'end_time': end_time,
                'duration_ms': end_ms - start_ms
            }
            
        except ValueError as e:
            return {
                'valid': False,
                'error': f'时间轴解析失败: {str(e)}',
                'timecode_line': timecode_line
            }
    
    def time_to_ms(self, time_str: str) -> int:
        """将时间字符串转换为毫秒"""
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_ms = parts[2].split(',')
        seconds = int(seconds_ms[0])
        milliseconds = int(seconds_ms[1])
        
        return hours * 3600 * 1000 + minutes * 60 * 1000 + seconds * 1000 + milliseconds
    
    def validate_subtitle_entry(self, entry_text: str, expected_number: int) -> Dict[str, Any]:
        """验证单个字幕条目"""
        lines = entry_text.strip().split('\n')
        
        if len(lines) < 2:
            return {
                'valid': False,
                'error': '字幕条目格式不完整，至少需要序号和时间轴两行',
                'lines': lines
            }
        
        # 验证序号
        try:
            entry_number = int(lines[0].strip())
            if entry_number != expected_number:
                return {
                    'valid': False,
                    'error': f'序号不匹配，期望 {expected_number}，实际 {entry_number}',
                    'expected': expected_number,
                    'actual': entry_number
                }
        except ValueError:
            return {
                'valid': False,
                'error': f'序号不是有效数字: {lines[0]}',
                'line': lines[0]
            }
        
        # 验证时间轴
        timecode_validation = self.validate_timecode_line(lines[1])
        if not timecode_validation['valid']:
            return timecode_validation
        
        # 验证字幕文本（可选，但至少要有内容）
        subtitle_text = '\n'.join(lines[2:]) if len(lines) > 2 else ''
        
        return {
            'valid': True,
            'number': entry_number,
            'start_time': timecode_validation['start_time'],
            'end_time': timecode_validation['end_time'],
            'duration_ms': timecode_validation['duration_ms'],
            'text': subtitle_text,
            'text_length': len(subtitle_text)
        }
    
    def check_time_overlaps(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """检查时间重叠问题"""
        overlaps = []
        
        for i in range(len(entries) - 1):
            current_entry = entries[i]
            next_entry = entries[i + 1]
            
            current_end_ms = self.time_to_ms(current_entry['end_time'])
            next_start_ms = self.time_to_ms(next_entry['start_time'])
            
            if current_end_ms > next_start_ms:
                overlaps.append({
                    'type': '时间重叠',
                    'entry1': current_entry['number'],
                    'entry2': next_entry['number'],
                    'overlap_ms': current_end_ms - next_start_ms,
                    'entry1_end': current_entry['end_time'],
                    'entry2_start': next_entry['start_time']
                })
        
        return overlaps
    
    def validate_complete_subtitle(self, subtitle_text: str) -> Dict[str, Any]:
        """
        完整的字幕格式验证
        这是主要的验证函数，纯粹的格式检查
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': {
                'total_entries': 0,
                'valid_entries': 0,
                'format_version': 'SRT',
                'encoding': 'UTF-8'
            },
            'entries': []
        }
        
        if not subtitle_text.strip():
            result['valid'] = False
            result['errors'].append('字幕内容为空')
            return result
        
        # 提取所有字幕条目
        entries = re.findall(self.entry_pattern, subtitle_text, re.DOTALL)
        
        if not entries:
            result['valid'] = False
            result['errors'].append('未找到有效的字幕条目')
            return result
        
        valid_entries = []
        expected_number = 1
        
        for i, (entry_num, timecode, text) in enumerate(entries):
            # 构建完整的条目文本
            full_entry = f"{entry_num}\n{timecode}\n{text}"
            
            # 验证条目
            entry_validation = self.validate_subtitle_entry(full_entry, expected_number)
            
            if not entry_validation['valid']:
                result['valid'] = False
                result['errors'].append({
                    'entry_number': expected_number,
                    'error': entry_validation['error'],
                    'context': entry_validation
                })
            else:
                valid_entries.append(entry_validation)
                result['info']['valid_entries'] += 1
            
            expected_number += 1
        
        result['info']['total_entries'] = len(entries)
        result['entries'] = valid_entries
        
        # 检查时间重叠（只在所有条目都有效时进行）
        if valid_entries and len(valid_entries) > 1:
            overlaps = self.check_time_overlaps(valid_entries)
            if overlaps:
                result['warnings'].extend(overlaps)
        
        # 检查序号连续性
        if len(entries) > 0:
            expected_numbers = set(range(1, len(entries) + 1))
            actual_numbers = {int(entry[0]) for entry in entries}
            missing_numbers = expected_numbers - actual_numbers
            extra_numbers = actual_numbers - expected_numbers
            
            if missing_numbers:
                result['warnings'].append({
                    'type': '序号缺失',
                    'missing': sorted(missing_numbers)
                })
            
            if extra_numbers:
                result['warnings'].append({
                    'type': '额外序号',
                    'extra': sorted(extra_numbers)
                })
        
        return result
    
    def format_validation_report(self, result: Dict[str, Any]) -> str:
        """格式化验证报告"""
        report = []
        report.append("字幕格式验证报告")
        report.append("=" * 40)
        
        if result['valid']:
            report.append("✅ 格式验证通过")
        else:
            report.append("❌ 格式验证失败")
        
        report.append(f"总条目数: {result['info']['total_entries']}")
        report.append(f"有效条目数: {result['info']['valid_entries']}")
        
        if result['errors']:
            report.append("\n错误:")
            for error in result['errors']:
                report.append(f"  - {error['error']}")
        
        if result['warnings']:
            report.append("\n警告:")
            for warning in result['warnings']:
                if isinstance(warning, dict):
                    if warning.get('type') == '时间重叠':
                        report.append(f"  - 条目{warning['entry1']}和{warning['entry2']}时间重叠{warning['overlap_ms']}ms")
                    elif warning.get('type') == '序号缺失':
                        report.append(f"  - 缺失序号: {warning['missing']}")
                    elif warning.get('type') == '额外序号':
                        report.append(f"  - 额外序号: {warning['extra']}")
                else:
                    report.append(f"  - {warning}")
        
        return "\n".join(report)


def main():
    """测试函数"""
    validator = SubtitleFormatValidator()
    
    # 测试数据
    test_subtitle = """1
00:00:00,000 --> 00:00:08,800
这是第一条字幕

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕

3
00:00:15,154 --> 00:00:20,000
这是第三条字幕"""
    
    result = validator.validate_complete_subtitle(test_subtitle)
    report = validator.format_validation_report(result)
    print(report)

if __name__ == "__main__":
    main()