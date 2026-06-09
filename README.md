# 有声书视频制作系统

PDF + 音频 + SRT 字幕 → 同步 MP4，支持卡拉OK逐字高亮。

## 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 基础用法

```bash
python create_video.py \
  --pdf in.pdf --audio in.m4a --subs in.srt \
  --output out.mp4
```

可选：`--start-page 5 --end-page 15` 限制页码范围。

## 卡拉OK逐字高亮（新增）

字幕不再显示在视频底部，而是**逐字覆盖在正文文字上**，随朗读进度推进。类似卡拉OK歌词跟随效果。

### 原理

1. 从 PDF 提取每个字的坐标（`page.get_text("words")`）
2. 将字幕文本匹配到 PDF 中的字符位置（模糊匹配）
3. 逐帧渲染：已读的字叠加青色半透明色块，色块随朗读进度逐个字推进
4. 同时底部保留字幕文字（黑底白字）
5. 帧数据通过管道直推 ffmpeg 编码，零磁盘 I/O

### 运行命令

```bash
python create_video.py \
  --pdf '电子书/红楼梦/原始文本/脂硯齋重評石頭記(曹雪芹脂砚斋).pdf' \
  --audio '电子书/红楼梦/音频文件/第一回【甄士隐梦幻识通灵贾雨村风尘怀闺秀】(上).m4a' \
  --subs '电子书/红楼梦/字幕文件/第一回【甄士隐梦幻识通灵贾雨村风尘怀闺秀】(上).srt' \
  --output 输出.mp4 \
  --start-page 15 --end-page 33 \
  --vertical --odd-right-even-left \
  --enable-highlight --karaoke --karaoke-fps 10
```

### 卡拉OK参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--enable-highlight` | 启用高亮功能（必选） | 关闭 |
| `--karaoke` | 启用逐字渐进高亮（不加则为静态指示线模式） | 关闭 |
| `--karaoke-fps` | 高亮刷新帧率，10=流畅，15=更流畅但生成更慢 | 12 |
| `--highlight-color` | 高亮色 RGBA，如 `0,200,255,220` | 青色半透明 |
| `--vertical` | 竖排双页布局（古籍用） | 关闭 |
| `--odd-right-even-left` | 奇数页在右、偶数页在左 | 关闭 |

### 静态指示线模式（`--enable-highlight` 不加 `--karaoke`）

在当前朗读句子的文字旁画一根指示线，句子级别跟随。

## 项目结构

```
有声书/
├── create_video.py          # 主入口，视频生成管线
├── app.py                   # Flask Web 界面
├── pdf_text_extractor.py    # PDF 文字坐标提取
├── subtitle_parser.py       # SRT 字幕解析
├── text_mapping_engine.py   # 字幕→PDF文字位置映射
├── indicator_renderer.py    # 指示线/卡拉OK渲染器
├── highlight_renderer.py    # 块级高亮渲染（旧）
├── video_composition_coordinator.py  # 编排器
├── config.py                # 全局配置
├── requirements.txt
├── 电子书/
│   └── [书名]/
│       ├── 原始文本/        # PDF
│       ├── 音频文件/        # .m4a/.mp3
│       ├── 字幕文件/        # .srt
│       ├── 有声读物/        # 生成 .mp4 + config.json
│       └── 配置信息/
```

## 核心依赖

- **PyMuPDF** (fitz) — PDF 渲染和文字提取
- **FFmpeg/ffprobe** — 视频编码、音频合并
- **Pillow** — 高亮色块渲染
- **faster-whisper** — 语音转字幕（可选）

## SRT 时间码兼容

支持非标准时间码格式（4-5 位毫秒），自动截取前 3 位。例如 `00:00:08,8000` 会被正确解析为 8.800 秒。

## 已知限制

- 文字匹配率约 52%（取决于 PDF 文字提取质量）
- 竖排双页渲染需要 `--odd-right-even-left` 参数配合古籍排版
- 字幕需与 PDF 文字内容匹配，OCR 质量差的 PDF 匹配率更低
