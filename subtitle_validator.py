#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕格式验证和修复工具
用于检测和修复SRT字幕文件中的时间轴格式问题
"""

import re
import os
import tempfile
from typing import Tuple, Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class SubtitleFormatValidator:
    """字幕格式验证和修复器"""

    def __init__(self):
        # 标准SRT时间轴格式: HH:MM:SS,mmm
        self.standard_timestamp_pattern = re.compile(r'^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})$')
        # 非标准格式: 检测毫秒位数不是3位的情况
        self.non_standard_timestamp_pattern = re.compile(r'^(\d{2}):(\d{2}):(\d{2}),(\d{4,5})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{4,5})$')
        # 通用时间轴匹配模式
        self.general_timestamp_pattern = re.compile(r'^(\d{2}):(\d{2}):(\d{2}),(\d+)\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d+)$')

    def validate_subtitle_format(self, subtitle_content: str) -> Dict[str, any]:
        """
        验证字幕文件格式

        Args:
            subtitle_content: 字幕文件内容

        Returns:
            验证结果字典
        """
        lines = subtitle_content.split('\n')
        total_lines = len(lines)
        invalid_timestamps = []
        fixed_timestamps = []
        needs_fix = False

        for i, line in enumerate(lines, 1):
            # 检查是否是时间轴行（包含 -->）
            if '-->' in line:
                # 检查是否符合标准格式
                if self.standard_timestamp_pattern.match(line.strip()):
                    continue  # 标准格式，无需修复
                elif self.general_timestamp_pattern.match(line.strip()):
                    # 非标准格式，需要修复
                    fixed_line = self._fix_timestamp_line(line.strip())
                    if fixed_line != line.strip():
                        invalid_timestamps.append({
                            'line_number': i,
                            'original': line.strip(),
                            'fixed': fixed_line
                        })
                        fixed_timestamps.append(fixed_line)
                        needs_fix = True
                else:
                    # 完全无法识别的格式
                    invalid_timestamps.append({
                        'line_number': i,
                        'original': line.strip(),
                        'fixed': None,
                        'error': '无法识别的时间轴格式'
                    })

        return {
            'is_valid': not needs_fix and len(invalid_timestamps) == 0,
            'needs_fix': needs_fix,
            'total_lines': total_lines,
            'invalid_count': len(invalid_timestamps),
            'invalid_timestamps': invalid_timestamps,
            'fixed_timestamps': fixed_timestamps
        }

    def _fix_timestamp_line(self, line: str) -> str:
        """
        修复单行时间轴格式 - 只修复毫秒位数，不修改时间值
        
        修复原则：
        1. 毫秒位数不足3位：补零
        2. 毫秒位数超过3位：截断（不进位）
        3. 保持原始时间值完全不变

        Args:
            line: 原始时间轴行

        Returns:
            修复后的时间轴行
        """
        match = self.general_timestamp_pattern.match(line.strip())
        if not match:
            return line

        # 提取时间组件
        start_h, start_m, start_s, start_ms = match.group(1), match.group(2), match.group(3), match.group(4)
        end_h, end_m, end_s, end_ms = match.group(5), match.group(6), match.group(7), match.group(8)

        # ✅ 正确修复：只修复毫秒位数，不修改时间值
        def fix_millisecond_format(ms_str):
            """修复毫秒格式，确保为3位，但保持数值不变"""
            if len(ms_str) == 3:
                return ms_str  # 已经是标准格式
            elif len(ms_str) < 3:
                return ms_str.ljust(3, '0')  # 补零
            else:  # len(ms_str) > 3
                return ms_str[:3]  # 截断，不进位
        
        # 修复毫秒格式
        start_ms_fixed = fix_millisecond_format(start_ms)
        end_ms_fixed = fix_millisecond_format(end_ms)
        
        # 构建修复后的时间字符串
        start_time_str = f"{start_h}:{start_m}:{start_s},{start_ms_fixed}"
        end_time_str = f"{end_h}:{end_m}:{end_s},{end_ms_fixed}"
        
        # 替换原行中的时间轴
        original_timestamp = f"{start_h}:{start_m}:{start_s},{start_ms} --> {end_h}:{end_m}:{end_s},{end_ms}"
        fixed_timestamp = f"{start_time_str} --> {end_time_str}"
        
        return line.replace(original_timestamp, fixed_timestamp)

    def _time_to_milliseconds(self, h: int, m: int, s: int, ms_str: str) -> int:
        """
        将时间转换为总毫秒数

        Args:
            h: 小时
            m: 分钟
            s: 秒
            ms_str: 毫秒字符串

        Returns:
            总毫秒数
        """
        ms = int(ms_str)
        return h * 3600000 + m * 60000 + s * 1000 + ms

    def _milliseconds_to_timestamp(self, total_ms: int) -> str:
        """
        将总毫秒数转换为标准时间戳格式

        Args:
            total_ms: 总毫秒数

        Returns:
            标准格式时间戳 HH:MM:SS,mmm
        """
        h = total_ms // 3600000
        total_ms %= 3600000
        m = total_ms // 60000
        total_ms %= 60000
        s = total_ms // 1000
        ms = total_ms % 1000

        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _fix_milliseconds(self, milliseconds: str) -> str:
        """
        修复毫秒格式，确保为3位

        Args:
            milliseconds: 原始毫秒字符串

        Returns:
            修复后的毫秒字符串（3位）
        """
        ms_int = int(milliseconds)

        # 如果毫秒数 >= 1000，需要进位到秒
        if ms_int >= 1000:
            # 转换为秒和毫秒
            seconds = ms_int // 1000
            ms_rem = ms_int % 1000

            # 返回修复后的完整时间格式（这个方法会在调用方处理）
            # 这里只返回毫秒部分，调用方会处理秒的进位
            return f"{ms_rem:03d}"
        else:
            # 补零到3位
            return f"{ms_int:03d}"

    def fix_subtitle_content(self, subtitle_content: str) -> Tuple[str, Dict[str, any]]:
        """
        修复字幕文件内容

        Args:
            subtitle_content: 原始字幕内容

        Returns:
            (修复后的内容, 修复报告)
        """
        validation_result = self.validate_subtitle_format(subtitle_content)

        if not validation_result['needs_fix']:
            return subtitle_content, {
                'fixed': False,
                'message': '字幕格式已经是标准格式，无需修复',
                'fixed_count': 0
            }

        # 执行修复
        lines = subtitle_content.split('\n')
        fixed_lines = []
        fix_map = {item['line_number'] - 1: item['fixed'] for item in validation_result['invalid_timestamps'] if item['fixed']}

        for i, line in enumerate(lines):
            if i in fix_map:
                fixed_lines.append(fix_map[i])
                logger.debug(f"第{i+1}行修复: {line.strip()} → {fix_map[i]}")
            else:
                fixed_lines.append(line)

        fixed_content = '\n'.join(fixed_lines)

        # 验证修复结果
        post_fix_validation = self.validate_subtitle_format(fixed_content)

        return fixed_content, {
            'fixed': True,
            'message': f"字幕格式修复完成，修复了 {validation_result['invalid_count']} 个时间轴",
            'fixed_count': validation_result['invalid_count'],
            'original_validation': validation_result,
            'post_fix_validation': post_fix_validation
        }

    def create_fixed_subtitle_file(self, subtitle_path: str, output_path: Optional[str] = None) -> Tuple[str, Dict[str, any]]:
        """
        创建修复后的字幕文件

        Args:
            subtitle_path: 原始字幕文件路径
            output_path: 输出文件路径，如果为None则自动生成

        Returns:
            (修复后的文件路径, 修复报告)
        """
        try:
            # 读取原始文件
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # 修复内容
            fixed_content, report = self.fix_subtitle_content(original_content)

            # 确定输出路径
            if output_path is None:
                base_name, ext = os.path.splitext(subtitle_path)
                output_path = f"{base_name}_fixed{ext}"

            # 写入修复后的文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)

            logger.info(f"字幕文件修复完成: {subtitle_path} → {output_path}")
            report['output_path'] = output_path

            return output_path, report

        except Exception as e:
            logger.error(f"字幕文件修复失败: {str(e)}")
            raise

    def validate_and_fix_in_memory(self, subtitle_content: bytes) -> Tuple[bytes, Dict[str, any]]:
        """
        在内存中验证和修复字幕内容（用于Web应用）

        Args:
            subtitle_content: 字幕文件字节数据

        Returns:
            (修复后的字节数据, 修复报告)
        """
        try:
            # 解码内容
            content_str = subtitle_content.decode('utf-8')

            # 修复内容
            fixed_content, report = self.fix_subtitle_content(content_str)

            # 重新编码
            fixed_bytes = fixed_content.encode('utf-8')

            return fixed_bytes, report

        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                content_str = subtitle_content.decode('gbk')
                fixed_content, report = self.fix_subtitle_content(content_str)
                fixed_bytes = fixed_content.encode('utf-8')
                report['encoding_detected'] = 'gbk'
                report['encoding_converted'] = 'utf-8'
                return fixed_bytes, report
            except:
                raise ValueError("无法解码字幕文件，请确保文件编码为UTF-8或GBK")
        except Exception as e:
            logger.error(f"内存字幕修复失败: {str(e)}")
            raise

def create_subtitle_validator():
    """创建字幕验证器实例"""
    return SubtitleFormatValidator()

# 测试函数
def test_subtitle_validator():
    """测试字幕验证器功能"""
    validator = SubtitleFormatValidator()

    # 测试非标准格式
    test_content = """1
00:00:00,000 --> 00:00:08,8000
测试字幕内容1

2
00:00:08,8000 --> 00:00:15,15440
测试字幕内容2

3
00:00:15,15440 --> 00:00:20,20000
测试字幕内容3
"""

    print("=== 字幕格式验证测试 ===")

    # 验证格式
    result = validator.validate_subtitle_format(test_content)
    print(f"验证结果: {result}")

    # 修复格式
    fixed_content, report = validator.fix_subtitle_content(test_content)
    print(f"修复报告: {report}")
    print(f"修复后的内容:\n{fixed_content}")

    # 验证修复结果
    post_validation = validator.validate_subtitle_format(fixed_content)
    print(f"修复后验证: {post_validation}")

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 运行测试
    test_subtitle_validator()