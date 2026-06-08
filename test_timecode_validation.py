#!/usr/bin/env python3
"""
测试时间轴验证功能
用于演示时间轴变化检测
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from deepseek_api import validate_timecodes, log_timecode_comparison
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_timecode_validation():
    """测试时间轴验证功能"""
    
    # 模拟用户提供的案例
    original_subtitle = """1
00:00:00,000 --> 00:00:08,8000
这是第一条字幕内容

2
00:00:08,8000 --> 00:00:15,15440
这是第二条字幕内容

3
00:00:15,15440 --> 00:00:25,00000
这是第三条字幕内容"""

    # 模拟DeepSeek API返回的结果（时间轴被修改）
    corrected_subtitle = """1
00:00:00,000 --> 00:00:16,000
这是第一条字幕内容（已校正）

2
00:00:16,000 --> 00:00:30,440
这是第二条字幕内容（已校正）

3
00:00:30,440 --> 00:00:40,00000
这是第三条字幕内容（已校正）"""

    logger.info("=" * 60)
    logger.info("时间轴验证测试")
    logger.info("=" * 60)
    
    logger.info("原始字幕:")
    logger.info(original_subtitle)
    logger.info("\n校正后字幕:")
    logger.info(corrected_subtitle)
    
    logger.info("\n" + "=" * 60)
    logger.info("开始验证时间轴完整性...")
    
    # 验证时间轴
    result = validate_timecodes(original_subtitle, corrected_subtitle)
    
    logger.info(f"验证结果: {result['message']}")
    logger.info(f"原始时间轴数量: {result['original_count']}")
    logger.info(f"校正后时间轴数量: {result['corrected_count']}")
    
    if result['changes']:
        logger.warning("发现以下时间轴变化:")
        for change in result['changes']:
            logger.warning(f"  第 {change['entry']} 条:")
            logger.warning(f"    原始: {change['original']}")
            logger.warning(f"    校正: {change['corrected']}")
            logger.warning(f"    变化类型: {change['change_type']}")
    
    # 记录详细对比信息
    log_timecode_comparison(original_subtitle, corrected_subtitle, "测试案例")
    
    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)
    
    return result

if __name__ == "__main__":
    test_timecode_validation()