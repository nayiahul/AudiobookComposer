#!/usr/bin/env python3
"""
对比测试：修复你的具体案例
展示旧修复逻辑的问题和新修复逻辑的正确性
"""

def old_broken_fix_logic(line):
    """模拟旧的错误修复逻辑"""
    import re
    
    # 提取时间组件（模拟旧逻辑）
    match = re.search(r'(\d{2}):(\d{2}):(\d{2}),(\d+)\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d+)', line)
    if not match:
        return line
    
    start_h, start_m, start_s, start_ms = match.group(1), match.group(2), match.group(3), match.group(4)
    end_h, end_m, end_s, end_ms = match.group(5), match.group(6), match.group(7), match.group(8)
    
    # 🔴 错误：直接将毫秒字符串当作数值处理
    start_total_ms = int(start_h) * 3600000 + int(start_m) * 60000 + int(start_s) * 1000 + int(start_ms)
    end_total_ms = int(end_h) * 3600000 + int(end_m) * 60000 + int(end_s) * 1000 + int(end_ms)
    
    # 转换回时间格式
    def ms_to_timestamp(total_ms):
        h = total_ms // 3600000
        total_ms %= 3600000
        m = total_ms // 60000
        total_ms %= 60000
        s = total_ms // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    start_fixed = ms_to_timestamp(start_total_ms)
    end_fixed = ms_to_timestamp(end_total_ms)
    
    return f"{start_fixed} --> {end_fixed}"

def new_correct_fix_logic(line):
    """新的正确修复逻辑"""
    import re
    
    # 匹配时间轴
    match = re.search(r'(\d{2}):(\d{2}):(\d{2}),(\d+)\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d+)', line)
    if not match:
        return line
    
    start_h, start_m, start_s, start_ms = match.group(1), match.group(2), match.group(3), match.group(4)
    end_h, end_m, end_s, end_ms = match.group(5), match.group(6), match.group(7), match.group(8)
    
    # ✅ 正确：只修复毫秒位数，不修改数值
    def fix_ms(ms_str):
        if len(ms_str) == 3:
            return ms_str
        elif len(ms_str) < 3:
            return ms_str.ljust(3, '0')
        else:  # len(ms_str) > 3
            return ms_str[:3]  # 截断，不进位
    
    start_ms_fixed = fix_ms(start_ms)
    end_ms_fixed = fix_ms(end_ms)
    
    start_time_fixed = f"{start_h}:{start_m}:{start_s},{start_ms_fixed}"
    end_time_fixed = f"{end_h}:{end_m}:{end_s},{end_ms_fixed}"
    
    return f"{start_time_fixed} --> {end_time_fixed}"

def test_your_case():
    """测试你的具体案例"""
    print("=== 对比测试：你的具体案例 ===\n")
    
    # 你的原始数据
    test_cases = [
        "00:00:00,000 --> 00:00:08,8000",
        "00:00:08,8000 --> 00:00:15,15440", 
        "00:00:15,15440 --> 00:00:20,20000"
    ]
    
    for i, original in enumerate(test_cases, 1):
        print(f"案例 {i}: {original}")
        print("-" * 50)
        
        # 旧逻辑结果
        old_result = old_broken_fix_logic(original)
        print(f"❌ 旧修复逻辑: {old_result}")
        
        # 新逻辑结果  
        new_result = new_correct_fix_logic(original)
        print(f"✅ 新修复逻辑: {new_result}")
        
        # 对比分析
        if old_result != new_result:
            print("🔍 差异分析:")
            print("  旧逻辑错误地将毫秒字符串当作数值处理")
            print("  新逻辑只修复格式，保持时间值不变")
        else:
            print("  两种逻辑结果相同")
        
        print()

if __name__ == "__main__":
    test_your_case()