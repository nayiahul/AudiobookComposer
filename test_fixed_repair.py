#!/usr/bin/env python3
"""
测试修复后的格式修复功能
验证只修复格式，不修改时间
"""

import sys
sys.path.append('/Users/nayiahlu/Documents/自研项目/python项目/有声书')

from subtitle_validator import SubtitleFormatValidator

def test_fixed_repair_function():
    """测试修复后的格式修复功能"""
    validator = SubtitleFormatValidator()
    
    print("=== 测试修复后的格式修复功能 ===\n")
    
    # 你的原始测试数据
    test_subtitle = """1
00:00:00,000 --> 00:00:08,8000
这是第一条字幕内容

2
00:00:08,8000 --> 00:00:15,15440
这是第二条字幕内容

3
00:00:15,15440 --> 00:00:20,20000
这是第三条字幕内容"""
    
    print("原始字幕内容:")
    print(test_subtitle)
    print("\n" + "="*60 + "\n")
    
    # 验证格式
    result = validator.validate_subtitle_format(test_subtitle)
    
    print(f"检测到问题数量: {result['invalid_count']}")
    print(f"需要修复: {result['needs_fix']}")
    
    if result['needs_fix'] and result['invalid_timestamps']:
        print("\n修复详情:")
        for i, fix in enumerate(result['invalid_timestamps'], 1):
            print(f"\n修复 {i}:")
            print(f"  行号: {fix['line_number']}")
            print(f"  修复前: {fix['original']}")
            print(f"  修复后: {fix['fixed']}")
            
            # 验证时间是否被修改
            original_start = fix['original'].split(' --> ')[0]
            fixed_start = fix['fixed'].split(' --> ')[0]
            original_end = fix['original'].split(' --> ')[1]
            fixed_end = fix['fixed'].split(' --> ')[1]
            
            # 提取时间部分（去掉毫秒）
            orig_start_time = ':'.join(original_start.split(':')[:-1]) + ':' + original_start.split(':')[-1].split(',')[0]
            fix_start_time = ':'.join(fixed_start.split(':')[:-1]) + ':' + fixed_start.split(':')[-1].split(',')[0]
            orig_end_time = ':'.join(original_end.split(':')[:-1]) + ':' + original_end.split(':')[-1].split(',')[0]
            fix_end_time = ':'.join(fixed_end.split(':')[:-1]) + ':' + fixed_end.split(':')[-1].split(',')[0]
            
            if orig_start_time == fix_start_time and orig_end_time == fix_end_time:
                print("  ✅ 时间值未被修改（只修复了毫秒格式）")
            else:
                print("  ❌ 时间值被修改了！")
    
    # 如果有修复，显示修复后的完整内容
    if result['needs_fix']:
        # 模拟修复过程
        fixed_content = test_subtitle
        for fix in reversed(result['invalid_timestamps']):
            lines = fixed_content.split('\n')
            line_idx = fix['line_number'] - 1
            if line_idx < len(lines):
                lines[line_idx] = fix['fixed']
                fixed_content = '\n'.join(lines)
        
        print("\n" + "="*60)
        print("修复后的完整字幕内容:")
        print(fixed_content)

if __name__ == "__main__":
    test_fixed_repair_function()