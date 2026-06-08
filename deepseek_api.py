#!/usr/bin/env python3
"""
DeepSeek API集成模块
用于调用DeepSeek进行字幕校正功能
"""

import os
import json
import time
import requests
from typing import Optional, Dict, Any
import logging

# 设置日志
logger = logging.getLogger(__name__)

class DeepSeekAPI:
    """DeepSeek API客户端类"""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.deepseek.com"):
        """
        初始化DeepSeek API客户端

        Args:
            api_key: DeepSeek API密钥，如果不提供则从环境变量获取
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

        # 设置默认请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Audiobook-Tool/1.0'
        })

        if self.api_key:
            self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})

    def set_api_key(self, api_key: str):
        """设置API密钥"""
        self.api_key = api_key
        self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})

    def _make_request(self, endpoint: str, data: Dict[str, Any], max_retries: int = 3, timeout: int = 120) -> Dict[str, Any]:
        """
        发送API请求

        Args:
            endpoint: API端点
            data: 请求数据
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）

        Returns:
            API响应数据

        Raises:
            Exception: 请求失败时抛出异常
        """
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(max_retries):
            try:
                logger.info(f"发送DeepSeek API请求 (尝试 {attempt + 1}/{max_retries}): {endpoint}")

                response = self.session.post(url, json=data, timeout=timeout)
                response.raise_for_status()

                result = response.json()
                logger.info(f"DeepSeek API请求成功，响应状态: {response.status_code}")
                return result

            except requests.exceptions.Timeout:
                logger.warning(f"DeepSeek API请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise Exception("DeepSeek API请求超时，请检查网络连接或稍后重试")
                time.sleep(2 ** attempt)  # 指数退避

            except requests.exceptions.HTTPError as e:
                error_msg = f"DeepSeek API请求失败: {e}"
                if response.status_code == 401:
                    error_msg += " - API密钥无效或未设置"
                elif response.status_code == 429:
                    error_msg += " - 请求频率过高，请稍后重试"
                elif response.status_code == 500:
                    error_msg += " - 服务器内部错误"
                else:
                    try:
                        error_detail = response.json().get('error', {}).get('message', '未知错误')
                        error_msg += f" - {error_detail}"
                    except:
                        error_msg += f" - HTTP {response.status_code}"

                logger.error(error_msg)
                if attempt == max_retries - 1 or response.status_code in [401, 403]:
                    raise Exception(error_msg)
                time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                logger.error(f"DeepSeek API请求异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise Exception(f"网络连接失败: {e}")
                time.sleep(2 ** attempt)

        raise Exception("DeepSeek API请求失败，已达到最大重试次数")

    def _correct_subtitle_in_batches(self, subtitle_text: str, original_text: str, enable_deepthink: bool = True, batch_size: int = 50) -> Dict[str, Any]:
        """
        分批处理字幕校正
        
        Args:
            batch_size: 每批处理的字幕条目数量
        """
        try:
            logger.info(f"开始分批字幕校正，每批{batch_size}条")
            start_time = time.time()
            
            # 分割字幕
            batches = self._split_subtitles(subtitle_text, max_entries=batch_size)
            
            # 逐批处理
            corrected_batches = []
            
            for i, batch in enumerate(batches):
                logger.info(f"处理第 {i+1}/{len(batches)} 批...")
                logger.info(f"第 {i+1} 批字幕长度: {len(batch)} 字符")
                
                # 尝试处理，最多重试2次
                max_retries = 2
                success = False
                result = None
                
                for retry in range(max_retries):
                    if retry > 0:
                        logger.info(f"第 {i+1} 批重试第 {retry} 次...")
                        time.sleep(2)
                    
                    result = self._correct_subtitle_single(batch, original_text, enable_deepthink)
                    
                    if result.get('success', False):
                        corrected_text = result.get('corrected_subtitle', '')
                        logger.info(f"第 {i+1} 批校正成功，长度: {len(corrected_text)} 字符")
                        
                        # 检查返回内容的前200字符
                        logger.info(f"第 {i+1} 批返回内容前200字符: {corrected_text[:200]}")
                        
                        # 检查是否和原始内容完全一样
                        if corrected_text.strip() == batch.strip():
                            logger.warning(f"⚠️ 第 {i+1} 批校正后内容与原始内容完全相同！")
                        
                        # 检查是否包含非字幕内容（如AI的解释）
                        if not corrected_text.strip().startswith(batch.split('\n')[0]):
                            logger.warning(f"⚠️ 第 {i+1} 批返回内容不是以序号开头，可能包含AI的解释文字")
                            logger.warning(f"期望开头: {batch.split(chr(10))[0]}")
                            logger.warning(f"实际开头: {corrected_text[:100]}")
                        
                        corrected_batches.append(corrected_text)
                        success = True
                        break
                    else:
                        logger.error(f"第 {i+1} 批失败（尝试 {retry+1}/{max_retries}）: {result.get('error')}")
                
                if not success:
                    logger.error(f"第 {i+1} 批处理失败，已重试{max_retries}次")
                    logger.error(f"失败批次前500字符: {batch[:500]}")
                    return {
                        "success": False,
                        "error": f"第 {i+1}/{len(batches)} 批处理失败，已重试{max_retries}次。建议减少每批数量。",
                        "failed_batch": i+1,
                        "total_batches": len(batches),
                        "original_subtitle": subtitle_text,
                        "reference_text": original_text
                    }
                
                # 批次间延迟
                if i < len(batches) - 1:
                    time.sleep(1)
            
            # 合并结果
            corrected_text = '\n\n'.join(corrected_batches)
            elapsed_time = time.time() - start_time
            
            # 验证合并后的时间轴完整性
            logger.info("开始验证合并结果的时间轴完整性...")
            validation_result = validate_timecodes(subtitle_text, corrected_text)
            
            if not validation_result["valid"]:
                logger.warning(f"⚠️ 分批校正时间轴验证失败: {validation_result['message']}")
                log_timecode_comparison(subtitle_text, corrected_text, "分批校正合并结果")
                logger.warning("尽管时间轴被修改，仍返回校正结果。建议用户检查时间轴变化。")
            else:
                logger.info("✓ 分批校正时间轴验证通过")
            
            logger.info(f"分批字幕校正完成，共{len(batches)}批，总耗时: {elapsed_time:.2f}秒")
            
            return {
                "success": True,
                "corrected_subtitle": corrected_text,
                "original_subtitle": subtitle_text,
                "reference_text": original_text,
                "processing_time": elapsed_time,
                "model_used": "deepseek-chat",
                "deepthink_enabled": enable_deepthink,
                "batch_count": len(batches),
                "timecode_validation": validation_result
            }
            
        except Exception as e:
            logger.error(f"分批字幕校正失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_subtitle": subtitle_text,
                "reference_text": original_text
            }
    
    def _split_subtitles(self, subtitle_text: str, max_entries: int = 100) -> list:
        """
        将字幕文本分割成多个批次
        
        Args:
            subtitle_text: 完整的字幕文本
            max_entries: 每批最多处理的字幕条目数
            
        Returns:
            字幕批次列表
        """
        import re
        
        # 按字幕条目分割（每个条目包含：序号、时间轴、文本、空行）
        # 使用正则表达式匹配字幕条目
        pattern = r'(\d+\n\d{2}:\d{2}:\d{2},\d+ --> \d{2}:\d{2}:\d{2},\d+\n.*?(?=\n\d+\n|\Z))'
        entries = re.findall(pattern, subtitle_text, re.DOTALL)
        
        logger.info(f"正则匹配到 {len(entries)} 条字幕")
        
        # 如果没有匹配到，尝试简单按序号分割
        if not entries:
            logger.warning("正则匹配失败，使用简单分割")
            parts = subtitle_text.split('\n\n')
            entries = [part for part in parts if part.strip()]
            logger.info(f"简单分割得到 {len(entries)} 个部分")
        
        # 分批
        batches = []
        for i in range(0, len(entries), max_entries):
            batch = '\n\n'.join(entries[i:i + max_entries])
            batches.append(batch)
            # 记录每批的第一条和最后一条序号
            first_line = batch.split('\n')[0]
            last_entry = entries[min(i + max_entries - 1, len(entries) - 1)]
            last_line = last_entry.split('\n')[0] if last_entry else "?"
            logger.info(f"第 {len(batches)} 批: 序号 {first_line} 到 {last_line}")
        
        logger.info(f"字幕分割完成: 总共{len(entries)}条，分成{len(batches)}批，每批最多{max_entries}条")
        return batches
    
    def correct_subtitle(self, subtitle_text: str, original_text: str, enable_deepthink: bool = True, batch_size: int = 50) -> Dict[str, Any]:
        """
        使用DeepSeek API校正字幕

        Args:
            subtitle_text: 待校正的字幕文本
            original_text: 原文参考文本
            enable_deepthink: 是否启用DeepThink功能
            batch_size: 每批处理的字幕条目数量（默认100）

        Returns:
            包含校正结果的字典
        """
        import re
        
        # 统计字幕条目数量
        subtitle_entries = re.findall(r'^\d+$', subtitle_text, re.MULTILINE)
        entry_count = len(subtitle_entries)
        
        # 如果字幕条目超过batch_size，自动分批处理
        if entry_count > batch_size:
            logger.info(f"字幕条目数量({entry_count})超过{batch_size}，启用分批处理模式")
            return self._correct_subtitle_in_batches(subtitle_text, original_text, enable_deepthink, batch_size)
        
        # 少于batch_size条，直接处理
        return self._correct_subtitle_single(subtitle_text, original_text, enable_deepthink)
    
    def _correct_subtitle_single(self, subtitle_text: str, original_text: str, enable_deepthink: bool = True) -> Dict[str, Any]:
        """
        单批次处理字幕校正
        """
        # 构建提示词
        prompt = self._build_subtitle_prompt(subtitle_text, original_text)

        # DeepSeek API的max_tokens上限是8192
        # 计算需要的token数量，但不超过8192
        estimated_tokens = min(8192, max(4096, int(len(subtitle_text) * 0.5)))
        
        # 构建请求数据
        request_data = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "temperature": 0.1,  # 低温度以获得更准确的结果
            "max_tokens": estimated_tokens  # 根据字幕长度动态设置，但不超过8192
        }
        
        logger.info(f"字幕长度: {len(subtitle_text)} 字符, 设置max_tokens: {estimated_tokens}")

        # 如果启用DeepThink，添加相关参数
        if enable_deepthink:
            request_data["reasoning_content"] = "请启用深度思考模式，仔细分析字幕文本和原文的差异，并进行精确校正。"

        try:
            logger.info("开始DeepSeek字幕校正")
            start_time = time.time()

            # 发送请求
            response = self._make_request("v1/chat/completions", request_data)

            # 解析响应
            corrected_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not corrected_text:
                raise Exception("DeepSeek API返回的校正结果为空")

            elapsed_time = time.time() - start_time
            
            # 验证时间轴是否被修改
            logger.info("开始验证时间轴完整性...")
            validation_result = validate_timecodes(subtitle_text, corrected_text)
            
            if not validation_result["valid"]:
                logger.warning(f"⚠️ 时间轴验证失败: {validation_result['message']}")
                
                # 记录详细的对比信息
                log_timecode_comparison(subtitle_text, corrected_text, "单批次校正")
                
                # 如果时间轴被修改，记录警告但继续返回结果
                # 用户可以选择是否接受这个结果
                logger.warning("尽管时间轴被修改，仍返回校正结果。建议用户检查时间轴变化。")
            else:
                logger.info("✓ 时间轴验证通过")
            
            logger.info(f"DeepSeek字幕校正完成，耗时: {elapsed_time:.2f}秒")

            return {
                "success": True,
                "corrected_subtitle": corrected_text,
                "original_subtitle": subtitle_text,
                "reference_text": original_text,
                "processing_time": elapsed_time,
                "model_used": "deepseek-chat",
                "deepthink_enabled": enable_deepthink,
                "timecode_validation": validation_result
            }

        except Exception as e:
            logger.error(f"DeepSeek字幕校正失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_subtitle": subtitle_text,
                "reference_text": original_text
            }

    def _build_subtitle_prompt(self, subtitle_text: str, original_text: str) -> str:
        """
        构建字幕校正的提示词

        Args:
            subtitle_text: 待校正的字幕文本
            original_text: 原文参考文本

        Returns:
            完整的提示词
        """
        # 统计字幕条目数量
        import re
        subtitle_entries = re.findall(r'^\d+$', subtitle_text, re.MULTILINE)
        entry_count = len(subtitle_entries)
        
        prompt = f"""你是一个专业的字幕校正专家。请根据提供的原文，校正以下字幕内容。

【核心要求 - 必须严格遵守】
输入字幕共有 {entry_count} 条，输出也必须是 {entry_count} 条！
绝对不允许合并、删除或增加任何字幕条目！
绝对不允许调整字幕内容的分布！

请根据第二段原文文本，对第一段字幕文本进行精确校对。具体要求如下：

1. **错别字校正**：【必须执行】
   - 必须校正每条字幕中的所有错别字
   - 对照原文，将错误的字替换为正确的字
   - 例如："真是以夢幻" → "甄士隱夢幻"，"加語尊" → "賈雨村"
   - 即使在原文中找不到完全对应的内容，也要根据上下文和常识校正明显的错别字
   - 不要因为找不到原文对应就直接返回原始字幕
   - 不要因为担心调整内容分布而不敢校正错别字
   - 校正错别字 ≠ 调整内容分布
   - 即使字幕被分成多条，每条都要独立校正其中的错别字

2. **标点符号补充**：
   - 根据原文添加标点符号
   - 但不要因为添加标点而改变字幕的内容分布
   - 保持每条字幕的原始内容范围

3. **格式保留**：严格保持第一段字幕文本的原始格式，包括：
   - 序号（如"1""2"等）- 必须从1到{entry_count}连续不断
   - 时间轴（如"00:00:03,550 --> 00:00:08,380"）- 完全不变
   - 文本行布局和换行 - 保持原样
   - 每条字幕的内容范围 - 不要扩展或缩减

4. **字数控制**：
   - 严格保持每条字幕的原始字数
   - 只替换错别字，不增加或删除文字
   - 不要把其他字幕的内容移到当前字幕

5. **条目数量保持**：【最重要】
   - 输入有 {entry_count} 条字幕
   - 输出必须有 {entry_count} 条字幕
   - 不得合并任何字幕条目（即使内容相关或来自同一句话）
   - 不得删除任何字幕条目（即使内容重复）
   - 不得增加任何字幕条目
   - 保持一一对应关系：第1条对第1条，第2条对第2条...第{entry_count}条对第{entry_count}条
   - 每条字幕只校正自己的内容，不要参考其他字幕

6. **内容分布保持**：【关键】
   - 不要根据原文的句子完整性来重新分配字幕内容
   - 每条字幕保持原有的内容范围
   - 即使原文是完整的一句话被分成多条字幕，也要保持分开
   - 不要把下一条字幕的内容提前到当前字幕
   - 不要把当前字幕的内容推迟到下一条字幕

7. **输出要求**：【严格遵守】
   - 直接返回完整的 {entry_count} 条字幕，不要添加任何说明文字
   - 不要在前面加"根据原文进行逐条校对，以下是校正后的字幕"等说明
   - 不要在后面加"校正完成"等总结
   - 第一行必须是序号"1"（或当前批次的起始序号）
   - 最后一行是第{entry_count}条的内容
   - 仅修改文字（错别字）和标点
   - 序号、时间轴、空行、内容范围完全保留

请逐条独立校对，每条字幕只校正自己的错别字，不要跨条目调整内容。
直接输出字幕，不要添加任何解释或说明。

以下是第一段字幕文本（待校对，共{entry_count}条）：
"""
        prompt += subtitle_text
        prompt += f"\n\n以下是第二段原文文本（校对基准）：\n"
        prompt += original_text
        prompt += f"\n\n【重要提醒】请严格按照上述要求对字幕进行校对，并返回完整的 {entry_count} 条校正结果。不要遗漏任何一条！"

        return prompt

    def test_connection(self) -> Dict[str, Any]:
        """
        测试API连接

        Returns:
            测试结果
        """
        try:
            # 发送简单的测试请求
            test_data = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": "请回复'连接测试成功'"
                    }
                ],
                "max_tokens": 50,
                "stream": False
            }

            logger.info("测试DeepSeek API连接")
            response = self._make_request("v1/chat/completions", test_data)

            if response.get("choices", [{}])[0].get("message", {}).get("content", ""):
                return {
                    "success": True,
                    "message": "DeepSeek API连接测试成功",
                    "model_available": "deepseek-chat"
                }
            else:
                return {
                    "success": False,
                    "message": "DeepSeek API返回异常响应"
                }

        except Exception as e:
            logger.error(f"DeepSeek API连接测试失败: {e}")
            return {
                "success": False,
                "message": f"DeepSeek API连接失败: {str(e)}"
            }

    def get_api_info(self) -> Dict[str, Any]:
        """
        获取API信息

        Returns:
            API信息字典
        """
        return {
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "api_key_prefix": self.api_key[:10] + "..." if self.api_key and len(self.api_key) > 10 else None,
            "supported_models": ["deepseek-chat"],
            "features": ["字幕校正", "深度思考模式"]
        }


# 全局DeepSeek API客户端实例
deepseek_client = None

def get_deepseek_client(api_key: Optional[str] = None) -> DeepSeekAPI:
    """
    获取DeepSeek API客户端实例

    Args:
        api_key: 可选的API密钥

    Returns:
        DeepSeekAPI客户端实例
    """
    global deepseek_client

    if deepseek_client is None or api_key:
        deepseek_client = DeepSeekAPI(api_key=api_key)

    return deepseek_client


def init_deepseek_from_config(config_path: str = "config.json"):
    """
    从配置文件初始化DeepSeek API

    Args:
        config_path: 配置文件路径
    """
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            deepseek_config = config.get('deepseek', {})
            api_key = deepseek_config.get('api_key')

            if api_key:
                get_deepseek_client(api_key)
                logger.info("从配置文件成功加载DeepSeek API配置")
            else:
                # 检查环境变量是否已有配置
                if os.getenv('DEEPSEEK_API_KEY'):
                    logger.info("使用环境变量中的DeepSeek API配置")
                    get_deepseek_client()
                else:
                    logger.warning("配置文件中未找到DeepSeek API密钥")
        else:
            # 检查环境变量是否已有配置
            if os.getenv('DEEPSEEK_API_KEY'):
                logger.info("使用环境变量中的DeepSeek API配置")
                get_deepseek_client()
            else:
                logger.warning(f"配置文件不存在: {config_path}")

    except Exception as e:
        logger.error(f"从配置文件初始化DeepSeek API失败: {e}")


def validate_timecodes(original_subtitle: str, corrected_subtitle: str) -> Dict[str, Any]:
    """
    验证字幕时间轴是否被修改
    
    Args:
        original_subtitle: 原始字幕文本
        corrected_subtitle: 校正后的字幕文本
        
    Returns:
        验证结果字典
    """
    import re
    
    # 提取时间轴的正则表达式
    timecode_pattern = r'\d{2}:\d{2}:\d{2},\d+ --> \d{2}:\d{2}:\d{2},\d+'
    
    # 从原始字幕中提取时间轴
    original_timecodes = re.findall(timecode_pattern, original_subtitle)
    
    # 从校正后的字幕中提取时间轴
    corrected_timecodes = re.findall(timecode_pattern, corrected_subtitle)
    
    # 检查时间轴数量是否一致
    if len(original_timecodes) != len(corrected_timecodes):
        logger.warning(f"时间轴数量不一致: 原始 {len(original_timecodes)} 条，校正后 {len(corrected_timecodes)} 条")
        return {
            "valid": False,
            "message": f"时间轴数量不一致: 原始 {len(original_timecodes)} 条，校正后 {len(corrected_timecodes)} 条",
            "original_count": len(original_timecodes),
            "corrected_count": len(corrected_timecodes),
            "changes": []
        }
    
    # 检查具体的时间轴变化
    changes = []
    for i, (orig, corr) in enumerate(zip(original_timecodes, corrected_timecodes)):
        if orig != corr:
            changes.append({
                "entry": i + 1,
                "original": orig,
                "corrected": corr,
                "change_type": "timecode_modified"
            })
            logger.warning(f"⚠️ 第 {i+1} 条字幕时间轴被修改: {orig} → {corr}")
    
    # 记录详细信息
    if changes:
        logger.warning(f"发现 {len(changes)} 处时间轴修改:")
        for change in changes:
            logger.warning(f"  第 {change['entry']} 条: {change['original']} → {change['corrected']}")
    
    return {
        "valid": len(changes) == 0,
        "message": f"发现 {len(changes)} 处时间轴修改" if changes else "时间轴验证通过",
        "original_count": len(original_timecodes),
        "corrected_count": len(corrected_timecodes),
        "changes": changes
    }


def log_timecode_comparison(original_subtitle: str, corrected_subtitle: str, context: str = ""):
    """
    记录时间轴对比信息用于调试
    
    Args:
        original_subtitle: 原始字幕文本
        corrected_subtitle: 校正后的字幕文本
        context: 上下文信息
    """
    import re
    
    # 提取字幕条目（包括序号、时间轴、文本）
    entry_pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d+ --> \d{2}:\d{2}:\d{2},\d+)\n(.*?(?=\n\d+\n|\Z))'
    
    original_entries = re.findall(entry_pattern, original_subtitle, re.DOTALL)
    corrected_entries = re.findall(entry_pattern, corrected_subtitle, re.DOTALL)
    
    logger.info(f"{context} - 时间轴对比分析:")
    logger.info(f"原始字幕条目数: {len(original_entries)}")
    logger.info(f"校正后字幕条目数: {len(corrected_entries)}")
    
    # 对比前5条字幕的时间轴
    for i in range(min(5, len(original_entries), len(corrected_entries))):
        orig_num, orig_time, orig_text = original_entries[i]
        corr_num, corr_time, corr_text = corrected_entries[i]
        
        if orig_time != corr_time:
            logger.warning(f"  条目 {orig_num}: 时间轴不同")
            logger.warning(f"    原始: {orig_time}")
            logger.warning(f"    校正: {corr_time}")
        else:
            logger.info(f"  条目 {orig_num}: 时间轴相同 ✓")
    
    # 如果存在大量时间轴变化，记录统计信息
    if len(original_entries) == len(corrected_entries):
        timecode_changes = sum(1 for i in range(len(original_entries)) 
                              if original_entries[i][1] != corrected_entries[i][1])
        if timecode_changes > 0:
            logger.warning(f"总共有 {timecode_changes}/{len(original_entries)} 条字幕时间轴被修改")