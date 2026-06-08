#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

# 测试数据
test_data = {
    "book_name": "测试书籍",
    "subtitle_filename": "test.srt",
    "start_page": 1,
    "end_page": 5,
    "is_vertical_layout": False,
    "page_content": [
        "这是第一页的内容，包含一些文字和描述。",
        "这是第二页的内容，讲述故事的开始。",
        "这是第三页的内容，主角登场了。",
        "这是第四页的内容，情节发展。",
        "这是第五页的内容，故事达到高潮。"
    ]
}

# 发送请求
response = requests.post(
    "http://localhost:5009/api/extract-timings-from-subtitles",
    json=test_data,
    headers={"Content-Type": "application/json"}
)

# 打印结果
print("状态码:", response.status_code)
print("响应内容:")
print(response.text)

# 尝试解析JSON响应
if response.status_code == 200:
    try:
        json_data = response.json()
        print("\n解析后的JSON数据:")
        print(json.dumps(json_data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\n解析JSON失败: {e}")
else:
    print(f"\n请求失败，状态码: {response.status_code}")
    print(f"响应头: {response.headers}")

# 如果状态码是400，尝试获取字幕内容以调试
if response.status_code == 400:
    print("\n尝试获取字幕内容进行调试...")
    subtitle_response = requests.get(
        'http://localhost:5009/api/get-subtitle-content',
        params={
            'book_name': test_data['book_name'],
            'subtitle_filename': test_data['subtitle_filename']
        }
    )
    print(f"获取字幕内容状态码: {subtitle_response.status_code}")
    print(f"获取字幕内容响应:")
    print(subtitle_response.text)
    
    # 尝试手动解析字幕文件
    print("\n尝试手动解析字幕文件...")
    subtitle_path = "/Users/nayiahlu/Documents/自研项目/python项目/有声书/电子书/测试书籍/字幕文件/美国家庭万用亲子英文8000句生活用语S01.srt"
    with open(subtitle_path, 'r', encoding='utf-8') as f:
        subtitle_content = f.read()
    
    # 打印前5个字幕块
    import re
    subtitle_blocks = re.split(r'\r?\n\r?\n', subtitle_content.strip())
    for i, block in enumerate(subtitle_blocks[:5]):
        print(f"字幕块 {i+1}:")
        print(block)
        print("---")