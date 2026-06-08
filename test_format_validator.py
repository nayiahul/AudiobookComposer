#!/usr/bin/env python3
"""
测试字幕格式校验器 - 演示各种格式错误检测
"""

from subtitle_format_validator import SubtitleFormatValidator

def test_format_validation():
    """测试各种格式错误"""
    validator = SubtitleFormatValidator()
    
    print("=== 字幕格式校验器测试 ===\n")
    
    # 测试1: 正确格式
    print("测试1: 正确格式")
    valid_subtitle = """1
00:00:00,000 --> 00:00:08,800
这是第一条字幕

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕"""
    
    result = validator.validate_complete_subtitle(valid_subtitle)
    print(validator.format_validation_report(result))
    print()
    
    # 测试2: 时间格式错误
    print("测试2: 时间格式错误")
    invalid_time_subtitle = """1
00:00:60,000 --> 00:00:08,800
这是第一条字幕

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕"""
    
    result = validator.validate_complete_subtitle(invalid_time_subtitle)
    print(validator.format_validation_report(result))
    print()
    
    # 测试3: 时间逻辑错误（结束早于开始）
    print("测试3: 时间逻辑错误")
    logical_error_subtitle = """1
00:00:10,000 --> 00:00:08,800
这是第一条字幕

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕"""
    
    result = validator.validate_complete_subtitle(logical_error_subtitle)
    print(validator.format_validation_report(result))
    print()
    
    # 测试4: 序号不连续
    print("测试4: 序号不连续")
    discontinuous_subtitle = """1
00:00:00,000 --> 00:00:08,800
这是第一条字幕

3
00:00:08,800 --> 00:00:15,154
这是第二条字幕"""
    
    result = validator.validate_complete_subtitle(discontinuous_subtitle)
    print(validator.format_validation_report(result))
    print()
    
    # 测试5: 时间重叠
    print("测试5: 时间重叠")
    overlap_subtitle = """1
00:00:00,000 --> 00:00:10,000
这是第一条字幕

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕"""
    
    result = validator.validate_complete_subtitle(overlap_subtitle)
    print(validator.format_validation_report(result))
    print()
    
    # 测试6: 格式完全不正确
    print("测试6: 格式完全不正确")
    broken_format_subtitle = """第一条字幕
00:00:00,000 -> 00:00:08,800
这是内容

2
00:00:08,800 --> 00:00:15,154
这是第二条字幕"""
    
    result = validator.validate_complete_subtitle(broken_format_subtitle)
    print(validator.format_validation_report(result))
    print()

if __name__ == "__main__":
    test_format_validation()