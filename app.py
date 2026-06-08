#!/usr/bin/env python3
"""
Web-based PDF to MP4 Video Creator with Custom Page Timings
"""

import os
import json
import subprocess
import sys
import tempfile
import threading
import time
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, Response
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Import torch for model info
import torch

# Import WhisperModel for model downloading and loading
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

# Import original Whisper for fallback
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Import our video creation functions
from create_video import (
    convert_pdf_to_images, get_audio_duration, create_silent_video,
    merge_audio_video, burn_subtitles, cleanup, check_ffmpeg,
    bake_subtitles_on_images
)

# Import subtitle format validator (延迟导入以优化启动性能)
# from subtitle_validator import SubtitleFormatValidator

# Import DeepSeek API for subtitle correction
from deepseek_api import get_deepseek_client, init_deepseek_from_config
# Import DeepSeek web interface for subtitle correction
# from deepseek_playwright_interface import DeepSeekPlaywrightInterface  # 已移动到bak目录，未使用


app = Flask(__name__)
from config import DEFAULT_SETTINGS, WHISPER_MODELS
app.config.update(DEFAULT_SETTINGS)

# 设置环境变量
if 'DEEPSEEK_API_KEY' in app.config:
    os.environ['DEEPSEEK_API_KEY'] = app.config['DEEPSEEK_API_KEY']

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# 配置JSON编码，使中文字符直接返回而不是Unicode编码
app.config['JSON_AS_ASCII'] = False

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Custom logging handler to emit logs to WebSocket clients
class WebSocketLogHandler(logging.Handler):
    def __init__(self, socketio_instance):
        super().__init__()
        self.socketio = socketio_instance
    
    def emit(self, record):
        try:
            # 只发送消息内容，不包含时间戳和日志级别前缀
            msg = record.getMessage()
            # 立即发送日志到前端，确保实时性
            self.socketio.emit('log_message', {
                'level': record.levelname,
                'message': msg,
                'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
            }, namespace='/')
            # 强制刷新事件队列，确保消息立即发送
            self.socketio.sleep(0)
        except Exception as e:
            # 打印错误到控制台以便调试
            print(f"WebSocket日志发送失败: {e}")
            self.handleError(record)

# 清除所有现有的处理器，避免重复
app.logger.handlers.clear()

# Add WebSocket log handler to Flask app logger
ws_handler = WebSocketLogHandler(socketio)
ws_handler.setLevel(logging.INFO)
app.logger.addHandler(ws_handler)
app.logger.setLevel(logging.INFO)

# 防止日志传播到父logger，避免重复
app.logger.propagate = False

# Ensure upload and output directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Global variables for job tracking
active_jobs: Dict[str, Dict] = {}

# Global variables for model download tracking
active_downloads: Dict[str, Dict] = {}  # 模型下载状态跟踪

def allowed_file(filename: str, allowed_extensions: List[str]) -> bool:
    """Check if file has allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_job_status(job_id: str) -> Dict:
    """Get current job status."""
    return active_jobs.get(job_id, {'status': 'not_found'})

def update_job_status(job_id: str, status: str, message: str = "", progress: int = 0):
    """Update job status."""
    if job_id in active_jobs:
        active_jobs[job_id].update({
            'status': status,
            'message': message,
            'progress': progress,
            'updated_at': datetime.now().isoformat()
        })

def cleanup_old_files():
    """Clean up old upload and output files (older than 24 hours)."""
    current_time = time.time()
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > 24 * 3600:  # 24 hours
                    try:
                        os.remove(file_path)
                        print(f"Cleaned up old file: {file_path}")
                    except Exception as e:
                        print(f"Failed to clean up {file_path}: {e}")

class MemoryVideoCreatorThread(threading.Thread):
    """Background thread for video creation using memory files."""

    def __init__(self, job_id: str, pdf_content: bytes, audio_content: bytes, subs_content: bytes, output_path: str, config: Dict):
        super().__init__()
        self.job_id = job_id
        self.pdf_content = pdf_content
        self.audio_content = audio_content
        self.subs_content = subs_content
        self.output_path = output_path
        self.config = config
        self.daemon = True  # Allow thread to exit when main program exits
        self.subtitle_validator = None  # 延迟初始化字幕验证器

    def run(self):
        """Execute video creation process."""
        try:
            update_job_status(self.job_id, 'processing', 'Starting video creation...', 0)

            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix=f"video_job_{self.job_id}_")
            update_job_status(self.job_id, 'processing', 'Creating temporary files...', 5)

            # Write memory content to temporary files
            pdf_temp_path = os.path.join(temp_dir, "temp.pdf")
            audio_temp_path = os.path.join(temp_dir, "temp.m4a")
            subs_temp_path = os.path.join(temp_dir, "temp.srt")

            with open(pdf_temp_path, 'wb') as f:
                f.write(self.pdf_content)

            with open(audio_temp_path, 'wb') as f:
                f.write(self.audio_content)

            # 验证和修复字幕格式（延迟加载验证器）
            update_job_status(self.job_id, 'processing', 'Validating subtitle format...', 7)
            try:
                # 延迟初始化字幕验证器
                if self.subtitle_validator is None:
                    from subtitle_validator import SubtitleFormatValidator
                    self.subtitle_validator = SubtitleFormatValidator()

                fixed_subs_content, subtitle_report = self.subtitle_validator.validate_and_fix_in_memory(self.subs_content)

                if subtitle_report.get('fixed', False):
                    app.logger.info(f"字幕格式已自动修复: {subtitle_report['message']}")
                    update_job_status(self.job_id, 'processing', f"Fixed {subtitle_report['fixed_count']} subtitle timestamps...", 8)
                else:
                    app.logger.info("字幕格式验证通过，无需修复")
                    update_job_status(self.job_id, 'processing', 'Subtitle format validated...', 8)

                # 使用修复后的字幕内容
                subs_content_to_write = fixed_subs_content

            except Exception as e:
                app.logger.warning(f"字幕格式验证失败，使用原始字幕: {str(e)}")
                update_job_status(self.job_id, 'processing', 'Using original subtitles (validation failed)...', 8)
                subs_content_to_write = self.subs_content

            with open(subs_temp_path, 'wb') as f:
                f.write(subs_content_to_write)

            update_job_status(self.job_id, 'processing', 'Temporary files created', 10)

            # Extract configuration
            start_page = self.config.get('start_page', 1)
            end_page = self.config.get('end_page')
            quality_preset = self.config.get('quality', 'medium')
            target_bitrate = self.config.get('bitrate', '1.5M')
            resolution = self.config.get('resolution')
            page_timings = self.config.get('page_timings', [])
            vertical_layout = self.config.get('vertical_layout', False)
            transition_effect = self.config.get('transition_effect', 'none')
            enable_highlight = self.config.get('enable_highlight', False)  # Phase 2: highlight option
            highlight_config_dict = self.config.get('highlight_config', {})  # Phase 2: highlight config

            # Step 1: Convert PDF to images (with optional text extraction for highlights)
            update_job_status(self.job_id, 'processing', 'Converting PDF to images...', 15)
            image_paths, text_data = convert_pdf_to_images(
                pdf_temp_path,
                temp_dir,
                start_page,
                end_page,
                vertical_layout,
                self.config.get('enable_crop', False),
                self.config.get('crop_settings', {}),
                self.config.get('odd_right_even_left', False),
                extract_text_data=enable_highlight  # Phase 2: extract text if highlight enabled
            )
            update_job_status(self.job_id, 'processing', f'Generated {len(image_paths)} images', 30)
            
            # Phase 2: Create highlighted frames if enabled
            if enable_highlight and text_data:
                try:
                    update_job_status(self.job_id, 'processing', 'Creating highlighted frames...', 35)
                    
                    # Import highlight modules
                    from highlight_renderer import HighlightConfig
                    
                    # Parse highlight config
                    highlight_color = tuple(highlight_config_dict.get('color', [255, 255, 0, 100]))
                    highlight_style = highlight_config_dict.get('style', 'background')
                    highlight_padding = highlight_config_dict.get('padding', 3)
                    
                    highlight_config = HighlightConfig(
                        color=highlight_color,
                        style=highlight_style,
                        padding=highlight_padding,
                        transition_duration=0.2
                    )
                    
                    # Create highlighted frames
                    from create_video import create_highlighted_video_frames
                    image_paths = create_highlighted_video_frames(
                        image_paths=image_paths,
                        subtitle_path=subs_temp_path,
                        audio_path=audio_temp_path,
                        text_data=text_data,
                        temp_dir=temp_dir,
                        highlight_config=highlight_config,
                        vertical_layout=vertical_layout
                    )
                    
                    update_job_status(self.job_id, 'processing', 'Highlighted frames created', 40)
                    app.logger.info(f"Highlight功能已应用，生成了 {len(image_paths)} 个高亮帧")
                    
                except Exception as e:
                    app.logger.warning(f"高亮渲染失败，使用原始图像: {e}")
                    update_job_status(self.job_id, 'processing', 'Highlight failed, using original images', 40)
            elif enable_highlight and not text_data:
                app.logger.warning("高亮功能已启用但文本提取失败")
                update_job_status(self.job_id, 'processing', 'Text extraction failed, highlight disabled', 35)

            # Calculate effective page timings for subtitle baking
            audio_duration = get_audio_duration(audio_temp_path)
            if page_timings and len(page_timings) == len(image_paths):
                effective_timings = list(page_timings)
            else:
                dur_per_page = audio_duration / len(image_paths)
                effective_timings = [dur_per_page] * len(image_paths)

            # Bake subtitles directly onto page images (avoids ffmpeg libass dependency)
            update_job_status(self.job_id, 'processing', 'Baking subtitles onto pages...', 42)
            first_img = __import__('PIL').Image.open(image_paths[0])
            image_paths, effective_timings = bake_subtitles_on_images(
                image_paths, subs_temp_path, effective_timings, temp_dir,
                video_width=first_img.width, video_height=first_img.height
            )

            # Step 2: Create silent video with custom timings
            update_job_status(self.job_id, 'processing', 'Creating video with subtitled pages...', 50)
            silent_video_path = self.create_silent_video_with_timings(
                image_paths, effective_timings, temp_dir, transition_effect
            )

            update_job_status(self.job_id, 'processing', 'Merging audio...', 60)

            # Step 3: Merge audio
            video_with_audio_path = merge_audio_video(silent_video_path, audio_temp_path, temp_dir)
            update_job_status(self.job_id, 'processing', 'Burning subtitles...', 80)

            # Step 4: Burn subtitles
            final_video_path = burn_subtitles(
                video_with_audio_path, subs_temp_path, self.output_path,
                quality_preset, target_bitrate, resolution
            )

            # 更新作业状态，包含output_path
            update_job_status(self.job_id, 'completed', 'Video creation completed!', 100)
            if self.job_id in active_jobs:
                active_jobs[self.job_id]['output_path'] = final_video_path

        except Exception as e:
            update_job_status(self.job_id, 'failed', f'Error: {str(e)}', 0)
            import traceback
            app.logger.error(f"视频创建失败: {str(e)}")
            app.logger.error(traceback.format_exc())
        finally:
            # Cleanup temporary files
            try:
                if 'temp_dir' in locals():
                    cleanup(temp_dir)
            except Exception as e:
                app.logger.error(f"Cleanup error: {e}")

    def create_silent_video_with_timings(self, image_paths: List[str], page_timings: List[float], temp_dir: str, transition_effect: str = 'none') -> str:
        """Create silent video with custom page timings and transition effects."""
        import subprocess

        # Create a concat file for FFmpeg
        concat_file = os.path.join(temp_dir, "filelist.txt")
        
        # 根据不同的翻页效果生成不同的FFmpeg命令
        if transition_effect == 'none':
            # 无效果，直接切换
            with open(concat_file, 'w') as f:
                for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {duration:.3f}\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        elif transition_effect == 'fade':
            # 淡入淡出效果
            # 创建带有淡入淡出效果的临时图片
            fade_images = []
            for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                # 为每个图片创建淡入淡出效果
                fade_img_path = os.path.join(temp_dir, f"fade_{i:03d}.png")
                fade_images.append(fade_img_path)
                
                # 使用FFmpeg添加淡入淡出效果
                fade_cmd = [
                    'ffmpeg',
                    '-i', img_path,
                    '-vf', 'fade=in:0:30,fade=out:st={duration-1}:d=1',
                    '-frames:v', '1',
                    fade_img_path
                ]
                subprocess.run(fade_cmd, capture_output=True, text=True, check=True)
            
            # 创建concat文件
            with open(concat_file, 'w') as f:
                for i, (fade_img_path, duration) in enumerate(zip(fade_images, page_timings)):
                    f.write(f"file '{fade_img_path}'\n")
                    f.write(f"duration {duration:.3f}\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        elif transition_effect == 'slide':
            # 滑动翻页效果
            # 创建临时视频文件，每个图片一个视频片段
            video_segments = []
            for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp4")
                video_segments.append(segment_path)
                
                # 为每个图片创建视频片段
                if i == 0:
                    # 第一张图片，从左侧滑入
                    segment_cmd = [
                        'ffmpeg',
                        '-loop', '1',
                        '-i', img_path,
                        '-t', str(duration),
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p',
                        '-c:v', 'libx264',
                        '-t', str(duration),
                        '-pix_fmt', 'yuv420p',
                        segment_path
                    ]
                else:
                    # 其他图片，从右侧滑入
                    segment_cmd = [
                        'ffmpeg',
                        '-loop', '1',
                        '-i', img_path,
                        '-t', str(duration),
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p',
                        '-c:v', 'libx264',
                        '-t', str(duration),
                        '-pix_fmt', 'yuv420p',
                        segment_path
                    ]
                subprocess.run(segment_cmd, capture_output=True, text=True, check=True)
            
            # 创建concat文件
            with open(concat_file, 'w') as f:
                for segment_path in video_segments:
                    f.write(f"file '{segment_path}'\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        elif transition_effect == 'flip':
            # 翻转效果
            # 创建临时视频文件，每个图片一个视频片段
            video_segments = []
            for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                segment_path = os.path.join(temp_dir, f"flip_segment_{i:03d}.mp4")
                video_segments.append(segment_path)
                
                # 为每个图片创建视频片段
                segment_cmd = [
                    'ffmpeg',
                    '-loop', '1',
                    '-i', img_path,
                    '-t', str(duration),
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p',
                    '-c:v', 'libx264',
                    '-t', str(duration),
                    '-pix_fmt', 'yuv420p',
                    segment_path
                ]
                subprocess.run(segment_cmd, capture_output=True, text=True, check=True)
            
            # 创建concat文件
            with open(concat_file, 'w') as f:
                for segment_path in video_segments:
                    f.write(f"file '{segment_path}'\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-filter_complex', '[0:v]split=2[v1][v2];[v1]format=yuv420p[v1f];[v2]format=yuv420p[v2f];[v1f][v2f]blend=all_expr=\'if(lt(on,1),A,if(lt(on,2),A*(2-on)+B*(on-1),B))\',pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        else:
            # 默认无效果
            with open(concat_file, 'w') as f:
                for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {duration:.3f}\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        app.logger.info(f"Custom timing video created with {transition_effect} effect: {result.stderr}")

        return silent_video_path

class VideoCreatorThread(threading.Thread):
    """Background thread for video creation."""

    def __init__(self, job_id: str, config: Dict):
        super().__init__()
        self.job_id = job_id
        self.config = config

    def run(self):
        """Execute video creation process."""
        try:
            update_job_status(self.job_id, 'processing', 'Starting video creation...', 0)

            # Extract configuration
            pdf_path = self.config['pdf_path']
            audio_path = self.config['audio_path']
            subs_path = self.config['subs_path']
            output_path = self.config['output_path']
            start_page = self.config.get('start_page', 1)
            end_page = self.config.get('end_page')
            quality_preset = self.config.get('quality', 'medium')
            target_bitrate = self.config.get('bitrate', '1.5M')
            resolution = self.config.get('resolution')
            page_timings = self.config.get('page_timings', [])
            vertical_layout = self.config.get('vertical_layout', False)  # 竖排布局选项
            odd_right_even_left = self.config.get('odd_right_even_left', False)  # 页面排列顺序
            transition_effect = self.config.get('transition_effect', 'none')  # 翻页效果选项
            enable_highlight = self.config.get('enable_highlight', False)  # Phase 2: highlight option
            highlight_config_dict = self.config.get('highlight_config', {})  # Phase 2: highlight config

            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix=f"video_job_{self.job_id}_")
            update_job_status(self.job_id, 'processing', 'Converting PDF to images...', 10)

            # Step 1: Convert PDF to images (with optional text extraction for highlights)
            image_paths, text_data = convert_pdf_to_images(
                pdf_path,
                temp_dir,
                start_page,
                end_page,
                vertical_layout,
                self.config.get('enable_crop', False),
                self.config.get('crop_settings', {}),
                odd_right_even_left,
                extract_text_data=enable_highlight  # Phase 2: extract text if highlight enabled
            )
            update_job_status(self.job_id, 'processing', f'Generated {len(image_paths)} images', 25)
            
            # Phase 2: Create highlighted frames if enabled
            if enable_highlight and text_data:
                try:
                    update_job_status(self.job_id, 'processing', 'Creating highlighted frames...', 30)
                    
                    # Import highlight modules
                    from highlight_renderer import HighlightConfig
                    
                    # Parse highlight config
                    highlight_color = tuple(highlight_config_dict.get('color', [255, 255, 0, 100]))
                    highlight_style = highlight_config_dict.get('style', 'background')
                    highlight_padding = highlight_config_dict.get('padding', 3)
                    
                    highlight_config = HighlightConfig(
                        color=highlight_color,
                        style=highlight_style,
                        padding=highlight_padding,
                        transition_duration=0.2
                    )
                    
                    # Create highlighted frames
                    from create_video import create_highlighted_video_frames
                    image_paths = create_highlighted_video_frames(
                        image_paths=image_paths,
                        subtitle_path=subs_path,
                        audio_path=audio_path,
                        text_data=text_data,
                        temp_dir=temp_dir,
                        highlight_config=highlight_config,
                        vertical_layout=vertical_layout
                    )
                    
                    update_job_status(self.job_id, 'processing', 'Highlighted frames created', 35)
                    print(f"Highlight功能已应用，生成了 {len(image_paths)} 个高亮帧")
                    
                except Exception as e:
                    print(f"Warning: 高亮渲染失败，使用原始图像: {e}")
                    update_job_status(self.job_id, 'processing', 'Highlight failed, using original images', 35)
            elif enable_highlight and not text_data:
                print("Warning: 高亮功能已启用但文本提取失败")
                update_job_status(self.job_id, 'processing', 'Text extraction failed, highlight disabled', 30)

            # Calculate effective page timings for subtitle baking
            audio_duration_vct = get_audio_duration(audio_path)
            if page_timings and len(page_timings) == len(image_paths):
                effective_timings = list(page_timings)
            else:
                dur_per_page = audio_duration_vct / len(image_paths)
                effective_timings = [dur_per_page] * len(image_paths)

            # Bake subtitles directly onto page images
            update_job_status(self.job_id, 'processing', 'Baking subtitles onto pages...', 37)
            first_img = __import__('PIL').Image.open(image_paths[0])
            image_paths, effective_timings = bake_subtitles_on_images(
                image_paths, subs_path, effective_timings, temp_dir,
                video_width=first_img.width, video_height=first_img.height
            )

            # Step 2: Create silent video with subtitle-baked images
            update_job_status(self.job_id, 'processing', 'Creating video with subtitled pages...', 45)
            silent_video_path = self.create_silent_video_with_timings(
                image_paths, effective_timings, temp_dir, transition_effect
            )

            update_job_status(self.job_id, 'processing', 'Merging audio...', 65)

            # Step 3: Merge audio (subtitles already baked into frames)
            video_with_audio_path = merge_audio_video(silent_video_path, audio_path, temp_dir)
            update_job_status(self.job_id, 'processing', 'Finalizing...', 85)

            # Step 4: Finalize (subtitles already in frames, just copy)
            final_video_path = burn_subtitles(
                video_with_audio_path, subs_path, output_path,
                quality_preset, target_bitrate, resolution
            )

            # 更新作业状态，包含output_path
            update_job_status(self.job_id, 'completed', 'Video creation completed!', 100)
            if self.job_id in active_jobs:
                active_jobs[self.job_id]['output_path'] = final_video_path

        except Exception as e:
            update_job_status(self.job_id, 'failed', f'Error: {str(e)}', 0)
        finally:
            # Cleanup temporary files
            try:
                if 'temp_dir' in locals():
                    cleanup(temp_dir)
            except Exception as e:
                print(f"Cleanup error: {e}")

    def create_silent_video_with_timings(self, image_paths: List[str], page_timings: List[float], temp_dir: str, transition_effect: str = 'none') -> str:
        """Create silent video with custom page timings and transition effects."""
        import subprocess

        # Create a concat file for FFmpeg
        concat_file = os.path.join(temp_dir, "filelist.txt")
        
        # 根据不同的翻页效果生成不同的FFmpeg命令
        if transition_effect == 'none':
            # 无效果，直接切换
            with open(concat_file, 'w') as f:
                for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {duration:.3f}\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        elif transition_effect == 'fade':
            # 淡入淡出效果
            # 创建带有淡入淡出效果的临时图片
            fade_images = []
            for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                # 为每个图片创建淡入淡出效果
                fade_img_path = os.path.join(temp_dir, f"fade_{i:03d}.png")
                fade_images.append(fade_img_path)
                
                # 使用FFmpeg添加淡入淡出效果
                fade_cmd = [
                    'ffmpeg',
                    '-i', img_path,
                    '-vf', 'fade=in:0:30,fade=out:st={duration-1}:d=1',
                    '-frames:v', '1',
                    fade_img_path
                ]
                subprocess.run(fade_cmd, capture_output=True, text=True, check=True)
            
            # 创建concat文件
            with open(concat_file, 'w') as f:
                for i, (fade_img_path, duration) in enumerate(zip(fade_images, page_timings)):
                    f.write(f"file '{fade_img_path}'\n")
                    f.write(f"duration {duration:.3f}\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        elif transition_effect == 'slide':
            # 滑动翻页效果
            # 创建临时视频文件，每个图片一个视频片段
            video_segments = []
            for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp4")
                video_segments.append(segment_path)
                
                # 为每个图片创建视频片段
                if i == 0:
                    # 第一张图片，从左侧滑入
                    segment_cmd = [
                        'ffmpeg',
                        '-loop', '1',
                        '-i', img_path,
                        '-t', str(duration),
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p',
                        '-c:v', 'libx264',
                        '-t', str(duration),
                        '-pix_fmt', 'yuv420p',
                        segment_path
                    ]
                else:
                    # 其他图片，从右侧滑入
                    segment_cmd = [
                        'ffmpeg',
                        '-loop', '1',
                        '-i', img_path,
                        '-t', str(duration),
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p',
                        '-c:v', 'libx264',
                        '-t', str(duration),
                        '-pix_fmt', 'yuv420p',
                        segment_path
                    ]
                subprocess.run(segment_cmd, capture_output=True, text=True, check=True)
            
            # 创建concat文件
            with open(concat_file, 'w') as f:
                for segment_path in video_segments:
                    f.write(f"file '{segment_path}'\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        elif transition_effect == 'flip':
            # 翻转效果
            # 创建临时视频文件，每个图片一个视频片段
            video_segments = []
            for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                segment_path = os.path.join(temp_dir, f"flip_segment_{i:03d}.mp4")
                video_segments.append(segment_path)
                
                # 为每个图片创建视频片段
                segment_cmd = [
                    'ffmpeg',
                    '-loop', '1',
                    '-i', img_path,
                    '-t', str(duration),
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p',
                    '-c:v', 'libx264',
                    '-t', str(duration),
                    '-pix_fmt', 'yuv420p',
                    segment_path
                ]
                subprocess.run(segment_cmd, capture_output=True, text=True, check=True)
            
            # 创建concat文件
            with open(concat_file, 'w') as f:
                for segment_path in video_segments:
                    f.write(f"file '{segment_path}'\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-filter_complex', '[0:v]split=2[v1][v2];[v1]format=yuv420p[v1f];[v2]format=yuv420p[v2f];[v1f][v2f]blend=all_expr=\'if(lt(on,1),A,if(lt(on,2),A*(2-on)+B*(on-1),B))\',pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]
        else:
            # 默认无效果
            with open(concat_file, 'w') as f:
                for i, (img_path, duration) in enumerate(zip(image_paths, page_timings)):
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {duration:.3f}\n")
            
            silent_video_path = os.path.join(temp_dir, "silent.mp4")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                silent_video_path
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Custom timing video created with {transition_effect} effect: {result.stderr}")

        return silent_video_path

@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')
    emit('status', {'msg': 'Connected to log stream'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')

@socketio.on('request_logs')
def handle_request_logs():
    """Send recent logs to newly connected client."""
    try:
        # Read recent log entries from app.log file
        log_file = 'app.log'
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Send last 50 lines
                for line in lines[-50:]:
                    if line.strip():
                        emit('log_message', {
                            'level': 'INFO',
                            'message': line.strip(),
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
    except Exception as e:
        app.logger.error(f"Error sending logs to client: {e}")

# FFmpeg 检查结果缓存
_ffmpeg_check_cache = {'result': None, 'timestamp': 0}

@app.route('/api/check-ffmpeg')
def check_ffmpeg_status():
    """Check if FFmpeg is available. Uses cache to avoid repeated checks."""
    import time
    current_time = time.time()
    
    # 如果缓存存在且未过期（60秒内），直接返回缓存结果
    if _ffmpeg_check_cache['result'] is not None and (current_time - _ffmpeg_check_cache['timestamp']) < 60:
        return jsonify({'available': _ffmpeg_check_cache['result']})
    
    # 执行检查并更新缓存
    result = check_ffmpeg()
    _ffmpeg_check_cache['result'] = result
    _ffmpeg_check_cache['timestamp'] = current_time
    
    return jsonify({'available': result})

@app.route('/api/subtitle_files')
def subtitle_files():
    """获取字幕文件列表"""
    try:
        subtitle_dir = 'subtitles'
        
        # 检查目录是否存在
        if not os.path.exists(subtitle_dir):
            return jsonify({'files': []})
        
        # 获取目录中的所有字幕文件
        files = []
        for filename in os.listdir(subtitle_dir):
            if filename.endswith(('.srt', '.SRT', '.txt', '.TXT')):
                file_path = os.path.join(subtitle_dir, filename)
                file_size = os.path.getsize(file_path)
                files.append({
                    'name': filename,
                    'size': file_size,
                    'path': file_path
                })
        
        return jsonify({'files': files})
        
    except Exception as e:
        app.logger.error(f'获取字幕文件列表失败: {e}')
        return jsonify({'error': f'Failed to get subtitle files: {str(e)}'}), 500

@app.route('/api/find-matching-subtitle', methods=['POST'])
def find_matching_subtitle():
    """Find a subtitle file that matches the audio filename."""
    try:
        data = request.get_json()
        book_name = data.get('book_name')
        audio_filename = data.get('audio_filename')
        possible_names = data.get('possible_names', [])
        
        app.logger.info(f'查找同名字幕文件请求: book_name={book_name}, audio_filename={audio_filename}, possible_names={possible_names}')
        
        if not book_name or not audio_filename:
            app.logger.error(f'缺少书名或音频文件名: book_name={book_name}, audio_filename={audio_filename}')
            return jsonify({'error': 'Missing book name or audio filename'}), 400
        
        # 构建输入文件保存目录：电子书/书名/有声读物
        input_dir = os.path.join('电子书', book_name, '有声读物')
        app.logger.info(f'查找字幕文件目录: {input_dir}')
        
        # 检查目录是否存在
        if not os.path.exists(input_dir):
            app.logger.warning(f'输入目录不存在: {input_dir}')
        
        # 在目录中查找匹配的字幕文件
        for filename in possible_names:
            file_path = os.path.join(input_dir, filename)
            app.logger.info(f'检查字幕文件: {file_path}')
            if os.path.exists(file_path):
                # 找到匹配的字幕文件
                file_size = os.path.getsize(file_path)
                app.logger.info(f'找到匹配的字幕文件: {file_path}, 大小: {file_size}')
                return jsonify({
                    'found': True,
                    'subtitle_name': filename,
                    'subtitle_path': file_path,
                    'file_size': file_size
                })
        
        # 如果没有找到完全匹配的字幕文件，尝试查找同名的不同扩展名文件
        base_name = os.path.splitext(audio_filename)[0]
        subtitle_extensions = ['.srt', '.SRT', '.txt', '.TXT']
        
        app.logger.info(f'未找到完全匹配的字幕文件，尝试基础名称+扩展名: base_name={base_name}')
        
        for ext in subtitle_extensions:
            possible_filename = base_name + ext
            file_path = os.path.join(input_dir, possible_filename)
            app.logger.info(f'检查字幕文件: {file_path}')
            if os.path.exists(file_path):
                # 找到匹配的字幕文件
                file_size = os.path.getsize(file_path)
                app.logger.info(f'找到匹配的字幕文件: {file_path}, 大小: {file_size}')
                return jsonify({
                    'found': True,
                    'subtitle_name': possible_filename,
                    'subtitle_path': file_path,
                    'file_size': file_size
                })
        
        # 如果在"有声读物"目录中未找到，尝试在"字幕文件"目录中查找
        subtitle_dir = os.path.join('电子书', book_name, '字幕文件')
        app.logger.info(f'在有声读物目录中未找到字幕文件，尝试在字幕文件目录中查找: {subtitle_dir}')
        
        # 检查字幕文件目录是否存在
        if not os.path.exists(subtitle_dir):
            app.logger.warning(f'字幕文件目录不存在: {subtitle_dir}')
            return jsonify({'found': False, 'message': 'No matching subtitle file found'})
        
        # 在字幕文件目录中查找匹配的字幕文件
        for filename in possible_names:
            file_path = os.path.join(subtitle_dir, filename)
            app.logger.info(f'检查字幕文件: {file_path}')
            if os.path.exists(file_path):
                # 找到匹配的字幕文件
                file_size = os.path.getsize(file_path)
                app.logger.info(f'在字幕文件目录中找到匹配的字幕文件: {file_path}, 大小: {file_size}')
                return jsonify({
                    'found': True,
                    'subtitle_name': filename,
                    'subtitle_path': file_path,
                    'file_size': file_size
                })
        
        # 如果没有找到完全匹配的字幕文件，尝试查找同名的不同扩展名文件
        app.logger.info(f'在字幕文件目录中未找到完全匹配的字幕文件，尝试基础名称+扩展名: base_name={base_name}')
        
        for ext in subtitle_extensions:
            possible_filename = base_name + ext
            file_path = os.path.join(subtitle_dir, possible_filename)
            app.logger.info(f'检查字幕文件: {file_path}')
            if os.path.exists(file_path):
                # 找到匹配的字幕文件
                file_size = os.path.getsize(file_path)
                app.logger.info(f'在字幕文件目录中找到匹配的字幕文件: {file_path}, 大小: {file_size}')
                return jsonify({
                    'found': True,
                    'subtitle_name': possible_filename,
                    'subtitle_path': file_path,
                    'file_size': file_size
                })

        # 没有找到匹配的字幕文件
        app.logger.info(f'未找到匹配的字幕文件')
        return jsonify({'found': False, 'message': 'No matching subtitle file found'})
        
    except Exception as e:
        app.logger.error(f'查找同名字幕文件失败: {e}')
        return jsonify({'error': f'Failed to find matching subtitle: {str(e)}'}), 500

@app.route('/api/load-subtitle-to-memory', methods=['POST'])
def load_subtitle_to_memory():
    """加载字幕文件到内存中"""
    try:
        data = request.get_json()
        book_name = data.get('book_name')
        subtitle_filename = data.get('subtitle_filename')
        
        if not book_name or not subtitle_filename:
            return jsonify({'error': 'Book name and subtitle filename are required'}), 400
        
        app.logger.info(f'加载字幕文件到内存: 书名={book_name}, 文件名={subtitle_filename}')
        
        # 构建字幕文件路径
        subtitle_path = os.path.join('电子书', book_name, '字幕文件', subtitle_filename)
        
        # 安全检查
        if '..' in subtitle_path or not os.path.abspath(subtitle_path).startswith(os.path.abspath('电子书')):
            return jsonify({'error': 'Invalid file path'}), 400
        
        # 检查文件是否存在
        if not os.path.exists(subtitle_path):
            return jsonify({'error': f'Subtitle file not found: {subtitle_filename}'}), 404
        
        # 读取文件内容
        with open(subtitle_path, 'rb') as f:
            file_content = f.read()
        
        file_size = len(file_content)
        
        # 确保内存文件字典存在
        if not hasattr(upload_file, 'memory_files'):
            upload_file.memory_files = {}
        
        # 生成文件键
        file_key = f"{book_name}_{subtitle_filename}"
        
        # 将文件内容存储在内存中
        upload_file.memory_files[file_key] = {
            'content': file_content,
            'filename': subtitle_filename,
            'file_type': 'subs',
            'book_name': book_name,
            'size': file_size
        }
        
        app.logger.info(f'字幕文件已加载到内存: {subtitle_filename}, 大小: {file_size} bytes')
        
        return jsonify({
            'success': True,
            'message': 'Subtitle file loaded to memory successfully',
            'file_key': file_key,
            'filename': subtitle_filename,
            'size': file_size
        })
        
    except Exception as e:
        app.logger.error(f'加载字幕文件到内存失败: {e}')
        return jsonify({'error': f'Failed to load subtitle to memory: {str(e)}'}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file uploads in memory without saving to disk."""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    uploaded_files = {}

    # 获取书名，如果没有提供则使用默认值
    book_name = request.form.get('book_name', '默认书籍')
    app.logger.info(f'上传文件，书名: {book_name}')

    for file in files:
        if file.filename == '':
            continue

        # Determine file type
        file_type = None
        if file.filename.lower().endswith('.pdf'):
            file_type = 'pdf'
            allowed = ['pdf']
        elif file.filename.lower().endswith(('.m4a', '.mp3', '.wav')):
            file_type = 'audio'
            allowed = ['m4a', 'mp3', 'wav']
        elif file.filename.lower().endswith(('.srt', '.txt')):
            file_type = 'subs'
            allowed = ['srt', 'txt']
        elif file.filename.lower().endswith(('.json', '.config')):
            file_type = 'config'
            allowed = ['json', 'config']
        elif file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')):
            file_type = 'video'
            allowed = ['mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv']
        else:
            app.logger.error(f'不支持的文件类型: {file.filename}')
            return jsonify({'error': f'Unsupported file type: {file.filename}'}), 400

        if not allowed_file(file.filename, allowed):
            app.logger.error(f'不允许的文件类型: {file.filename}')
            return jsonify({'error': f'File type not allowed: {file.filename}'}), 400

        # 读取文件内容到内存
        file_content = file.read()
        file_size = len(file_content)
        
        # 生成文件标识符（使用原始文件名）
        filename = secure_filename(file.filename)
        original_filename = file.filename  # 保存原始文件名
        
        # 将文件内容存储在内存中（使用全局字典）
        if not hasattr(upload_file, 'memory_files'):
            upload_file.memory_files = {}
        
        # 使用书名和文件名作为键存储文件内容
        file_key = f"{book_name}_{filename}"
        upload_file.memory_files[file_key] = {
            'content': file_content,
            'filename': filename,
            'original_filename': original_filename,  # 保存原始文件名
            'file_type': file_type,
            'book_name': book_name,
            'size': file_size
        }
        
        # 对于配置文件，同时保存到磁盘以便预览功能正常工作
        if file_type == 'config':
            try:
                # 处理书名，去掉括号及括号后的内容
                clean_book_name = book_name.split('(')[0].strip()
                
                # 构建配置目录路径：电子书/书名/有声读物
                config_dir = os.path.join('电子书', clean_book_name, '有声读物')
                os.makedirs(config_dir, exist_ok=True)
                
                # 保存配置文件到磁盘
                config_file_path = os.path.join(config_dir, filename)
                with open(config_file_path, 'wb') as f:
                    f.write(file_content)
                
                app.logger.info(f'配置文件已保存到磁盘: {config_file_path}')
            except Exception as e:
                app.logger.error(f'保存配置文件到磁盘失败: {e}')
        
        app.logger.info(f'文件已加载到内存: {filename}, 大小: {file_size} bytes')

        uploaded_files[file_type] = {
            'name': file.filename,
            'filename': filename,
            'size': file_size,
            'file_key': file_key,  # 使用文件键而不是路径
            'key': file_key,  # 同时提供key字段以保持一致性
            'book_name': book_name
        }
        
        app.logger.info(f'添加文件到uploaded_files: {file_type} -> {file.filename}')

    # Return success even if not all files are uploaded
    # The frontend will track which files have been uploaded
    app.logger.info(f'上传完成，返回文件信息: {uploaded_files}')
    return jsonify({
        'message': 'Files uploaded successfully',
        'files': uploaded_files,
        'book_name': book_name
    })

@app.route('/api/get-pdf-pages', methods=['POST'])
def get_pdf_pages():
    """Get PDF page count for timing configuration."""
    data = request.get_json()
    pdf_path = data.get('pdf_path')
    
    # 如果没有提供PDF路径，尝试从内存文件中获取
    if not pdf_path and hasattr(upload_file, 'memory_files'):
        # 查找PDF文件
        for file_key, file_info in upload_file.memory_files.items():
            if file_info['file_type'] == 'pdf':
                # 创建临时文件
                temp_dir = tempfile.mkdtemp()
                temp_pdf_path = os.path.join(temp_dir, "temp.pdf")
                
                # 将内存中的内容写入临时文件
                with open(temp_pdf_path, 'wb') as f:
                    f.write(file_info['content'])
                
                # 设置清理回调
                def cleanup_temp_files():
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                    except Exception as e:
                        app.logger.error(f'清理临时文件失败: {e}')
                
                # 注册清理回调
                response = jsonify({'temp_path': temp_pdf_path})
                response.call_on_close(cleanup_temp_files)
                
                pdf_path = temp_pdf_path
                break
    
    # 如果仍然没有PDF路径，尝试使用默认路径
    if not pdf_path:
        book_name = data.get('book_name', '默认书籍')
        config_dir = os.path.join('电子书', book_name, '配置信息')
        pdf_path = os.path.join(config_dir, 'default.pdf')
    
    app.logger.info('最终使用的PDF路径: %s', pdf_path)
    app.logger.debug('收到配置参数: pdf_path=%s audio_filename=%s subtitle_filename=%s',
                  data.get('pdf_path'), data.get('audio_filename'), data.get('subtitle_filename'))

    if not pdf_path or not os.path.exists(pdf_path):
        return jsonify({'error': 'PDF file not found'}), 400

    try:
        import fitz
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()

        # 检查是否存在配置文件
        book_name = data.get('book_name', '默认书籍')
        config_dir = os.path.join('电子书', book_name, '配置信息')
        config_file = os.path.join(config_dir, 'page_timings.json')
        
        suggested_timings = None
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    suggested_timings = config_data.get('page_timings', [])
                    # 确保配置文件中的时间点数量与页面数量匹配
                    if len(suggested_timings) != page_count:
                        suggested_timings = None
            except Exception as e:
                app.logger.error(f'读取配置文件失败: {e}')
                suggested_timings = None
        
        # 如果没有有效的配置文件，返回空数组
        if suggested_timings is None:
            suggested_timings = []
        
        return jsonify({
            'page_count': page_count,
            'suggested_timings': suggested_timings
        })

    except Exception as e:
        return jsonify({'error': f'Failed to read PDF: {str(e)}'}), 500

@app.route('/api/create-video', methods=['POST'])
def create_video():
    """Start video creation process."""
    data = request.get_json()

    # Validate required fields
    required_fields = ['pdf_key', 'audio_key', 'subs_key', 'output_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # 从内存中获取文件内容
    pdf_key = data['pdf_key']
    audio_key = data['audio_key']
    subs_key = data['subs_key']
    
    # 检查内存中是否存在这些文件
    if not hasattr(upload_file, 'memory_files'):
        return jsonify({'error': 'No files in memory. Please upload files first.'}), 400
    
    memory_files = upload_file.memory_files
    
    # 查找PDF文件，如果找不到确切匹配，尝试匹配文件名
    pdf_file_key = None
    if pdf_key in memory_files:
        pdf_file_key = pdf_key
    else:
        # 尝试匹配文件名
        for key, file_info in memory_files.items():
            if file_info['file_type'] == 'pdf' and (file_info['filename'] == pdf_key or key.endswith(f"_{pdf_key}")):
                pdf_file_key = key
                break
    
    if pdf_file_key is None:
        return jsonify({'error': f'PDF file not found in memory: {pdf_key}'}), 400
    
    # 查找音频文件，如果找不到确切匹配，尝试匹配文件名
    audio_file_key = None
    if audio_key in memory_files:
        audio_file_key = audio_key
    else:
        # 尝试匹配文件名
        for key, file_info in memory_files.items():
            if file_info['file_type'] == 'audio' and (file_info['filename'] == audio_key or key.endswith(f"_{audio_key}")):
                audio_file_key = key
                break
    
    if audio_file_key is None:
        return jsonify({'error': f'Audio file not found in memory: {audio_key}'}), 400
    
    # 查找字幕文件，如果找不到确切匹配，尝试匹配文件名
    subs_file_key = None
    if subs_key in memory_files:
        subs_file_key = subs_key
        app.logger.info(f'找到确切匹配的字幕文件: {subs_key}')
    else:
        # 尝试匹配文件名
        app.logger.info(f'未找到确切匹配的字幕文件: {subs_key}，尝试匹配文件名')
        app.logger.info(f'内存中的文件: {list(memory_files.keys())}')
        for key, file_info in memory_files.items():
            app.logger.info(f'检查文件: {key}, 类型: {file_info["file_type"]}, 文件名: {file_info["filename"]}')
            if file_info['file_type'] == 'subs' and (file_info['filename'] == subs_key or key.endswith(f"_{subs_key}")):
                subs_file_key = key
                app.logger.info(f'找到匹配的字幕文件: {key}')
                break
    
    if subs_file_key is None:
        return jsonify({'error': f'Subtitle file not found in memory: {subs_key}'}), 400
    
    # 获取文件内容
    pdf_content = memory_files[pdf_file_key]['content']
    audio_content = memory_files[audio_file_key]['content']
    subs_content = memory_files[subs_file_key]['content']
    
    # 获取书名，用于确定输出目录
    book_name = data.get('book_name', '默认书籍')
    
    # 生成输出文件名
    job_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    
    # 确定输出目录：与书籍目录同级的"有声读物"目录
    if book_name:
        # 构建输出目录路径
        output_dir = os.path.join('电子书', book_name, '有声读物')
        os.makedirs(output_dir, exist_ok=True)
        
        # 改进输出文件名生成逻辑，确保与字幕文件名保持一致
        # 1. 获取字幕文件名（不含扩展名）
        subtitle_filename = memory_files.get(subs_file_key, {}).get('filename', '')
        subtitle_base_name = os.path.splitext(subtitle_filename)[0] if subtitle_filename else ''
        
        # 2. 优先使用字幕文件名作为视频文件名基础
        if subtitle_base_name and subtitle_base_name != '':
            output_name = f"{subtitle_base_name}.mp4"
        else:
            # 如果无法获取字幕文件名，使用提供的output_name
            output_name = secure_filename(data['output_name'])
            # 确保文件名有.mp4扩展名
            if not output_name.lower().endswith('.mp4'):
                # 如果文件名已经是"mp4"或以点开头，则使用默认名称
                if output_name.lower() == 'mp4' or output_name.startswith('.'):
                    output_name = 'video.mp4'
                else:
                    output_name = f"{os.path.splitext(output_name)[0]}.mp4"
        
        # 3. 如果文件已存在，添加时间戳
        output_path = os.path.join(output_dir, output_name)
        if os.path.exists(output_path):
            name_without_ext = os.path.splitext(output_name)[0]
            # 如果文件名为空或只有扩展名，使用默认名称
            if not name_without_ext or name_without_ext == '':
                name_without_ext = 'video'
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_name = f"{name_without_ext}_{timestamp}.mp4"
            output_path = os.path.join(output_dir, output_name)
    else:
        # 回退到原来的输出目录
        output_name = secure_filename(data['output_name'])
        if not output_name.lower().endswith('.mp4'):
            output_name += '.mp4'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{job_id}_{output_name}")
    
    # 创建视频配置
    config = {
        'start_page': data.get('start_page', 1),
        'end_page': data.get('end_page'),
        'quality': data.get('quality', 'medium'),
        'bitrate': data.get('bitrate', '1.5M'),
        'resolution': data.get('resolution'),
        'page_timings': data.get('page_timings', []),
        'vertical_layout': data.get('vertical_layout', False),  # 竖排布局选项
        'odd_right_even_left': data.get('odd_right_even_left', False),  # 页面排列顺序
        'transition_effect': data.get('transition_effect', 'none'),  # 翻页效果选项
        'enable_crop': data.get('enable_crop', False),  # PDF边界裁剪选项
        'crop_settings': data.get('crop_settings', {}),  # 裁剪设置
        # Phase 2: Highlight configuration
        'enable_highlight': data.get('enable_highlight', False),  # 是否启用高亮功能
        'highlight_config': data.get('highlight_config', {
            'color': [255, 255, 0, 100],  # 默认黄色半透明
            'style': 'background',  # 默认背景高亮
            'padding': 3  # 默认3像素padding
        })
    }

    # Initialize job status
    active_jobs[job_id] = {
        'status': 'queued',
        'message': 'Job queued for processing...',
        'progress': 0,
        'created_at': datetime.now().isoformat(),
        'config': config
    }

    # 创建内存处理视频线程
    thread = MemoryVideoCreatorThread(
        job_id=job_id,
        pdf_content=pdf_content,
        audio_content=audio_content,
        subs_content=subs_content,
        output_path=output_path,
        config=config
    )
    thread.start()

    return jsonify({
        'job_id': job_id,
        'message': 'Video creation started',
        'estimated_time': 'Varies based on file size and quality settings',
        'output_path': output_path
    })

@app.route('/api/job-status/<job_id>')
def job_status(job_id):
    """Get job status."""
    status = get_job_status(job_id)
    if status['status'] == 'not_found':
        return jsonify({'error': 'Job not found'}), 404

    # Add download URL if completed
    if status['status'] == 'completed' and 'output_filename' not in status:
        # 获取输出文件路径
        output_path = status.get('output_path', '')
        if output_path:
            # 从输出路径中提取书名和文件名
            path_parts = output_path.split(os.sep)
            if '电子书' in path_parts:
                ebook_index = path_parts.index('电子书')
                if len(path_parts) > ebook_index + 2:
                    book_name = path_parts[ebook_index + 1]
                    filename = os.path.basename(output_path)
                    status['output_filename'] = filename
                    status['book_name'] = book_name
                    status['download_url'] = f'/download/{book_name}/{filename}'
                    status['preview_url'] = f'/api/video-preview/{book_name}/{filename}'

    return jsonify(status)

@app.route('/download/<path:book_name>/<filename>')
def download_file(book_name, filename):
    """Download a generated video file."""
    # 对URL编码的书名和文件名进行解码
    from urllib.parse import unquote
    book_name = unquote(book_name)
    filename = unquote(filename)
    
    # 构建文件路径：电子书/书名/有声读物/文件名
    file_path = os.path.join('电子书', book_name, '有声读物', filename)
    
    # 安全检查：确保文件路径在预期的目录内
    if not os.path.abspath(file_path).startswith(os.path.abspath(os.path.join('电子书', book_name, '有声读物'))):
        return jsonify({'error': 'Invalid file path'}), 403
    
    # 检查文件是否存在
    if not os.path.isfile(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # 返回文件
    return send_file(file_path, as_attachment=True)

@app.route('/api/video-preview/<path:book_name>/<filename>')
def video_preview(book_name, filename):
    """Preview a generated video file or audio file."""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)
        
        # 首先尝试从内存中获取音频文件
        if hasattr(upload_file, 'memory_files'):
            file_key = f"{book_name}_{filename}"
            if file_key in upload_file.memory_files:
                # 从内存中获取音频文件内容
                audio_data = upload_file.memory_files[file_key]['content']
                
                # 创建临时文件
                temp_dir = tempfile.mkdtemp()
                temp_audio_path = os.path.join(temp_dir, "temp_audio")
                
                with open(temp_audio_path, 'wb') as f:
                    f.write(audio_data)
                
                # 确定MIME类型
                mime_type = 'audio/mpeg'  # 默认MP3
                if filename.lower().endswith('.wav'):
                    mime_type = 'audio/wav'
                elif filename.lower().endswith('.ogg'):
                    mime_type = 'audio/ogg'
                elif filename.lower().endswith('.aac'):
                    mime_type = 'audio/aac'
                elif filename.lower().endswith('.flac'):
                    mime_type = 'audio/flac'
                
                # 返回临时音频文件
                response = send_file(temp_audio_path, mimetype=mime_type)
                
                # 设置回调函数，在请求完成后删除临时文件
                @response.call_on_close
                def _cleanup():
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                    except Exception as e:
                        app.logger.error(f"清理临时音频文件失败: {e}")
                
                return response
        
        # 如果内存中没有，尝试从磁盘读取
        # 构建文件路径 - 首先尝试音频文件目录
        file_path = os.path.join('电子书', book_name, '音频文件', filename)
        
        # 安全检查
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'error': 'Invalid file path'}), 400
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            # 如果找不到文件，尝试查找名为'mp3'的文件（这是上传API保存的方式）
            mp3_file_path = os.path.join('电子书', book_name, '音频文件', 'mp3')
            if os.path.exists(mp3_file_path):
                file_path = mp3_file_path
            else:
                # 如果音频文件目录中没有，尝试有声读物目录（兼容旧版本）
                old_file_path = os.path.join('电子书', book_name, '有声读物', filename)
                if os.path.exists(old_file_path):
                    file_path = old_file_path
                else:
                    old_mp3_file_path = os.path.join('电子书', book_name, '有声读物', 'mp3')
                    if os.path.exists(old_mp3_file_path):
                        file_path = old_mp3_file_path
                    else:
                        # 如果不是音频文件，尝试作为视频文件处理
                        video_path = os.path.join('电子书', book_name, '有声读物', filename)
                        
                        # 安全检查：确保文件路径在预期的目录内
                        if not os.path.abspath(video_path).startswith(os.path.abspath(os.path.join('电子书', book_name, '有声读物'))):
                            return jsonify({'error': 'Invalid file path'}), 403
                        
                        # 检查文件是否存在
                        if not os.path.isfile(video_path):
                            # 如果找不到文件，尝试查找常见的视频文件名
                            video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
                            for ext in video_extensions:
                                alt_path = os.path.join('电子书', book_name, '有声读物', f'video{ext}')
                                if os.path.isfile(alt_path):
                                    video_path = alt_path
                                    break
                            else:
                                # 如果没有找到任何视频文件，尝试查找名为'mp4'的文件（这是上传API保存的方式）
                                mp4_file_path = os.path.join('电子书', book_name, '有声读物', 'mp4')
                                if os.path.isfile(mp4_file_path):
                                    video_path = mp4_file_path
                                else:
                                    return jsonify({'error': 'File not found'}), 404
                        
                        # 返回视频文件用于预览（不作为附件下载）
                        return send_file(video_path)
        
        # 确定MIME类型
        mime_type = 'audio/mpeg'  # 默认MP3
        if filename.lower().endswith('.wav'):
            mime_type = 'audio/wav'
        elif filename.lower().endswith('.ogg'):
            mime_type = 'audio/ogg'
        elif filename.lower().endswith('.aac'):
            mime_type = 'audio/aac'
        elif filename.lower().endswith('.flac'):
            mime_type = 'audio/flac'
        
        # 返回音频文件
        return send_file(file_path, mimetype=mime_type)
    except Exception as e:
        app.logger.error('音频/视频预览失败: %s', e)
        return jsonify({'error': f'Failed to preview audio/video: {str(e)}'}), 500

@app.route('/api/pdf-preview/<path:book_name>/<filename>')
def pdf_preview(book_name, filename):
    """Preview PDF file."""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)
        
        # 首先尝试从内存中获取PDF文件
        if hasattr(upload_file, 'memory_files'):
            file_key = f"{book_name}_{filename}"
            if file_key in upload_file.memory_files:
                # 从内存中获取PDF文件内容
                pdf_data = upload_file.memory_files[file_key]['content']
                
                # 创建临时文件
                temp_dir = tempfile.mkdtemp()
                temp_pdf_path = os.path.join(temp_dir, "temp.pdf")
                
                with open(temp_pdf_path, 'wb') as f:
                    f.write(pdf_data)
                
                # 返回临时PDF文件
                response = send_file(temp_pdf_path, mimetype='application/pdf')
                
                # 设置回调函数，在请求完成后删除临时文件
                @response.call_on_close
                def _cleanup():
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                    except Exception as e:
                        app.logger.error(f"清理临时PDF文件失败: {e}")
                
                return response
        
        # 如果内存中没有，尝试从磁盘读取
        # 构建文件路径 - 首先尝试原始文本目录
        file_path = os.path.join('电子书', book_name, '原始文本', filename)
        
        # 安全检查
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'error': 'Invalid file path'}), 400
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            # 如果找不到文件，尝试查找名为'pdf'的文件（这是上传API保存的方式）
            pdf_file_path = os.path.join('电子书', book_name, '原始文本', 'pdf')
            if os.path.exists(pdf_file_path):
                file_path = pdf_file_path
            else:
                # 如果原始文本目录中没有，尝试有声读物目录（兼容旧版本）
                old_file_path = os.path.join('电子书', book_name, '有声读物', filename)
                if os.path.exists(old_file_path):
                    file_path = old_file_path
                else:
                    old_pdf_file_path = os.path.join('电子书', book_name, '有声读物', 'pdf')
                    if os.path.exists(old_pdf_file_path):
                        file_path = old_pdf_file_path
                    else:
                        return jsonify({'error': 'File not found'}), 404
        
        # 返回PDF文件
        return send_file(file_path, mimetype='application/pdf')
    except Exception as e:
        app.logger.error('PDF预览失败: %s', e)
        return jsonify({'error': f'Failed to preview PDF: {str(e)}'}), 500

@app.route('/api/subs-content/<path:book_name>/<filename>')
def subs_content(book_name, filename):
    """Get subtitle file content."""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)
        
        # 首先尝试从内存中获取字幕文件
        if hasattr(upload_file, 'memory_files'):
            file_key = f"{book_name}_{filename}"
            if file_key in upload_file.memory_files:
                # 从内存中获取字幕文件内容
                subs_data = upload_file.memory_files[file_key]['content']
                
                # 解码内容（假设是UTF-8编码）
                try:
                    content = subs_data.decode('utf-8')
                except UnicodeDecodeError:
                    # 如果UTF-8解码失败，尝试其他编码
                    try:
                        content = subs_data.decode('gbk')
                    except UnicodeDecodeError:
                        content = subs_data.decode('latin-1')
                
                return jsonify({
                    'content': content,
                    'filename': filename
                })
        
        # 如果内存中没有，尝试从磁盘读取
        # 构建文件路径 - 首先尝试字幕文件目录
        file_path = os.path.join('电子书', book_name, '字幕文件', filename)
        
        # 安全检查
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'error': 'Invalid file path'}), 400
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            # 如果找不到指定的字幕文件，尝试从音频文件名推断字幕文件名
            # 字幕文件名应与音频文件名保持一致，仅后缀不同
            audio_file_path = os.path.join('电子书', book_name, '音频文件')
            if os.path.exists(audio_file_path):
                # 查找音频文件目录中的音频文件
                audio_files = [f for f in os.listdir(audio_file_path) 
                              if f.lower().endswith(('.m4a', '.mp3', '.wav', '.aac', '.flac', '.ogg'))]
                if audio_files:
                    # 使用第一个音频文件的名称构建字幕文件名
                    audio_filename = audio_files[0]
                    subtitle_filename = os.path.splitext(audio_filename)[0] + '.srt'
                    inferred_subtitle_path = os.path.join('电子书', book_name, '字幕文件', subtitle_filename)
                    if os.path.exists(inferred_subtitle_path):
                        file_path = inferred_subtitle_path
                        app.logger.info(f'通过音频文件名推断字幕文件: {subtitle_filename}')
                    else:
                        return jsonify({'error': 'Subtitle file not found'}), 404
                else:
                    return jsonify({'error': 'No audio files found to infer subtitle name'}), 404
            else:
                return jsonify({'error': 'Subtitle file not found and no audio directory'}), 404
        
        # 读取字幕文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
        
        # 创建响应并确保中文字符不被转义
        response = app.response_class(
            response=json.dumps({
                'content': content,
                'filename': filename
            }, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )
        return response
    except Exception as e:
        app.logger.error('字幕内容加载失败: %s', e)
        return jsonify({'error': f'Failed to load subtitle content: {str(e)}'}), 500

@app.route('/api/fix-subtitle/<path:book_name>/<filename>', methods=['POST'])
def fix_subtitle(book_name, filename):
    """修复字幕文件格式并保存"""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)

        subtitle_content = None
        file_key = f"{book_name}_{filename}"

        # 首先尝试从内存中获取字幕文件
        if hasattr(upload_file, 'memory_files'):
            if file_key in upload_file.memory_files:
                # 从内存中获取字幕文件内容
                subs_data = upload_file.memory_files[file_key]['content']

                # 解码内容
                try:
                    subtitle_content = subs_data.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        subtitle_content = subs_data.decode('gbk')
                    except UnicodeDecodeError:
                        subtitle_content = subs_data.decode('latin-1')

        # 如果内存中没有，尝试从磁盘读取
        if subtitle_content is None:
            file_path = os.path.join('电子书', book_name, '字幕文件', filename)

            # 安全检查
            if '..' in file_path or file_path.startswith('/'):
                return jsonify({'error': 'Invalid file path'}), 400

            if not os.path.exists(file_path):
                return jsonify({'error': f'Subtitle file not found: {filename}'}), 404

            # 读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    subtitle_content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        subtitle_content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        subtitle_content = f.read()

        # 修复字幕格式
        try:
            from subtitle_validator import SubtitleFormatValidator
            validator = SubtitleFormatValidator()
            fixed_content, fix_report = validator.fix_subtitle_content(subtitle_content)
        except ImportError:
            return jsonify({'error': 'Subtitle validation module not available'}), 500

        # 保存修复后的字幕
        # 1. 保存到磁盘
        file_path = os.path.join('电子书', book_name, '字幕文件', filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        # 2. 更新内存中的内容
        if hasattr(upload_file, 'memory_files') and file_key in upload_file.memory_files:
            upload_file.memory_files[file_key]['content'] = fixed_content.encode('utf-8')
        
        # 记录详细的修复信息到日志
        app.logger.info(f'字幕文件已修复并保存: {filename}, 修复了 {fix_report.get("fixed_count", 0)} 处问题')
        app.logger.info('=' * 60)
        app.logger.info('修复详情：')
        
        # 从原始验证结果中获取详细信息
        if 'original_validation' in fix_report and 'invalid_timestamps' in fix_report['original_validation']:
            invalid_items = fix_report['original_validation']['invalid_timestamps']
            for i, item in enumerate(invalid_items[:10], 1):
                app.logger.info(f'  {i}. 第 {item["line_number"]} 行:')
                app.logger.info(f'     修复前: {item["original"]}')
                app.logger.info(f'     修复后: {item["fixed"]}')
            if len(invalid_items) > 10:
                app.logger.info(f'  ... 还有 {len(invalid_items) - 10} 处修复')
        
        # 显示修复后的验证结果
        if 'post_fix_validation' in fix_report:
            post_validation = fix_report['post_fix_validation']
            if post_validation['is_valid']:
                app.logger.info('✅ 修复后验证通过，所有时间轴格式正确')
            else:
                app.logger.warning(f'⚠️ 修复后仍有 {post_validation["invalid_count"]} 处问题')
        
        app.logger.info('=' * 60)

        return jsonify({
            'success': True,
            'message': f'字幕已修复并保存，共修复 {fix_report.get("fixed_count", 0)} 处问题',
            'fix_report': fix_report
        })

    except Exception as e:
        app.logger.error(f'修复字幕文件失败: {str(e)}')
        return jsonify({'error': f'Failed to fix subtitle: {str(e)}'}), 500

@app.route('/api/validate-subtitle/<path:book_name>/<filename>')
def validate_subtitle(book_name, filename):
    """验证字幕文件格式"""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)

        subtitle_content = None

        # 首先尝试从内存中获取字幕文件
        if hasattr(upload_file, 'memory_files'):
            file_key = f"{book_name}_{filename}"
            if file_key in upload_file.memory_files:
                # 从内存中获取字幕文件内容
                subs_data = upload_file.memory_files[file_key]['content']

                # 解码内容
                try:
                    subtitle_content = subs_data.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        subtitle_content = subs_data.decode('gbk')
                    except UnicodeDecodeError:
                        subtitle_content = subs_data.decode('latin-1')

        # 如果内存中没有，尝试从磁盘读取
        if subtitle_content is None:
            file_path = os.path.join('电子书', book_name, '字幕文件', filename)

            # 安全检查
            if '..' in file_path or file_path.startswith('/'):
                return jsonify({'error': 'Invalid file path'}), 400

            if not os.path.exists(file_path):
                return jsonify({'error': f'Subtitle file not found: {filename}'}), 404

            # 读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    subtitle_content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        subtitle_content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        subtitle_content = f.read()

        # 验证字幕格式（延迟加载）
        try:
            from subtitle_validator import SubtitleFormatValidator
            validator = SubtitleFormatValidator()
            validation_result = validator.validate_subtitle_format(subtitle_content)
        except ImportError:
            return jsonify({'error': 'Subtitle validation module not available'}), 500

        # 如果需要修复，提供修复后的内容预览和详细日志
        preview_content = None
        if validation_result['needs_fix']:
            try:
                fixed_content, fix_report = validator.fix_subtitle_content(subtitle_content)

                # 只提供前5个修复条目的预览
                lines = fixed_content.split('\n')
                preview_lines = []
                line_count = 0
                for line in lines:
                    preview_lines.append(line)
                    if line.strip().isdigit() or '-->' in line:
                        line_count += 1
                        if line_count >= 10:  # 最多显示5个条目（每个条目最多2行）
                            break

                preview_content = '\n'.join(preview_lines)

                # 添加修复报告
                validation_result['fix_report'] = fix_report
                validation_result['preview'] = preview_content
                
                # 记录详细的问题清单到日志
                app.logger.info(f'字幕校验完成：发现 {validation_result["invalid_count"]} 处格式问题')
                app.logger.info('=' * 60)
                app.logger.info('问题详情：')
                for i, item in enumerate(validation_result['invalid_timestamps'][:10], 1):
                    app.logger.info(f'  {i}. 第 {item["line_number"]} 行:')
                    app.logger.info(f'     原始: {item["original"]}')
                    app.logger.info(f'     修复: {item["fixed"]}')
                if validation_result['invalid_count'] > 10:
                    app.logger.info(f'  ... 还有 {validation_result["invalid_count"] - 10} 处问题')
                app.logger.info('=' * 60)

            except Exception as e:
                app.logger.error(f'字幕修复预览失败: {str(e)}')
                validation_result['fix_error'] = str(e)

        # 创建响应
        response = app.response_class(
            response=json.dumps(validation_result, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )
        return response

    except Exception as e:
        app.logger.error(f'字幕验证失败: {str(e)}')
        return jsonify({'error': f'Subtitle validation failed: {str(e)}'}), 500

@app.route('/api/config-content/<path:book_name>/<filename>')
def config_content(book_name, filename):
    """配置内容API"""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)
        
        # 构建配置文件路径 - 首先尝试有声读物目录
        file_path = os.path.join('电子书', book_name, '有声读物', filename)
        
        # 安全检查
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            # 如果找不到文件，尝试查找名为'config'的文件（这是上传API保存的方式）
            config_file_path = os.path.join('电子书', book_name, '有声读物', 'config')
            if os.path.exists(config_file_path):
                file_path = config_file_path
            else:
                # 如果有声读物目录中没有配置文件，尝试从配置信息目录查找
                # 处理书名，去掉括号及括号后的内容
                clean_book_name = book_name.split('(')[0].strip()
                config_dir = os.path.join('电子书', clean_book_name, '配置信息')
                
                # 检查配置信息目录是否存在
                if os.path.exists(config_dir):
                    # 查找config.json文件
                    config_json_path = os.path.join(config_dir, 'config.json')
                    if os.path.exists(config_json_path):
                        file_path = config_json_path
                    else:
                        # 如果没有config.json，查找任何.json文件
                        json_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
                        if json_files:
                            file_path = os.path.join(config_dir, json_files[0])
                        else:
                            app.logger.error(f'配置文件不存在: {file_path}')
                            return jsonify({'error': 'File not found'}), 404
                else:
                    app.logger.error(f'配置文件不存在: {file_path}')
                    return jsonify({'error': 'File not found'}), 404
        
        # 读取配置文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
        
        # 尝试解析为JSON，如果失败则返回原始文本
        try:
            json_content = json.loads(content)
            # 创建响应并确保中文字符不被转义
            response = app.response_class(
                response=json.dumps(json_content, ensure_ascii=False),
                status=200,
                mimetype='application/json'
            )
            return response
        except json.JSONDecodeError:
            # 创建响应并确保中文字符不被转义
            response = app.response_class(
                response=json.dumps({'content': content}, ensure_ascii=False),
                status=200,
                mimetype='application/json'
            )
            return response
    except Exception as e:
        app.logger.error(f'配置内容错误: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs')
def list_jobs():
    """List recent jobs - 不再被前端使用，保留用于调试和监控"""
    jobs = []
    for job_id, job_data in active_jobs.items():
        jobs.append({
            'job_id': job_id,
            **job_data
        })

    # Sort by creation time (newest first)
    jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    return jsonify({'jobs': jobs[:20]})  # Return last 20 jobs

@app.route('/api/input-file/<path:book_name>/<filename>')
def serve_input_file(book_name, filename):
    """Serve input files from the appropriate directory based on file type."""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)
        
        # 首先尝试从内存中获取文件
        if hasattr(upload_file, 'memory_files'):
            file_key = f"{book_name}_{filename}"
            if file_key in upload_file.memory_files:
                # 从内存中获取文件内容
                file_data = upload_file.memory_files[file_key]['content']
                
                # 创建临时文件
                temp_dir = tempfile.mkdtemp()
                temp_file_path = os.path.join(temp_dir, "temp_file")
                
                with open(temp_file_path, 'wb') as f:
                    f.write(file_data)
                
                # 确定MIME类型
                mime_type = 'application/octet-stream'  # 默认二进制流
                if filename.lower().endswith('.pdf'):
                    mime_type = 'application/pdf'
                elif filename.lower().endswith(('.m4a', '.mp3')):
                    mime_type = 'audio/mpeg'
                elif filename.lower().endswith('.wav'):
                    mime_type = 'audio/wav'
                elif filename.lower().endswith('.ogg'):
                    mime_type = 'audio/ogg'
                elif filename.lower().endswith('.aac'):
                    mime_type = 'audio/aac'
                elif filename.lower().endswith('.flac'):
                    mime_type = 'audio/flac'
                elif filename.lower().endswith(('.srt', '.txt')):
                    mime_type = 'text/plain'
                
                # 返回临时文件
                response = send_file(temp_file_path, mimetype=mime_type)
                
                # 设置回调函数，在请求完成后删除临时文件
                @response.call_on_close
                def _cleanup():
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                    except Exception as e:
                        app.logger.error(f"清理临时文件失败: {e}")
                
                return response
        
        # 如果内存中没有，尝试从磁盘读取
        # 根据文件类型确定目录
        if filename.lower().endswith('.pdf'):
            # PDF文件在原始文本目录
            file_path = os.path.join('电子书', book_name, '原始文本', filename)
            alt_path = os.path.join('电子书', book_name, '原始文本', 'pdf')
        elif filename.lower().endswith(('.m4a', '.mp3', '.wav')):
            # 音频文件在音频文件目录
            file_path = os.path.join('电子书', book_name, '音频文件', filename)
            alt_path = os.path.join('电子书', book_name, '音频文件', 'm4a')
        elif filename.lower().endswith(('.srt', '.txt')):
            # 字幕文件在字幕文件目录
            file_path = os.path.join('电子书', book_name, '字幕文件', filename)
            alt_path = os.path.join('电子书', book_name, '字幕文件', 'srt')
        else:
            # 其他文件默认在有声读物目录
            file_path = os.path.join('电子书', book_name, '有声读物', filename)
            alt_path = None
        
        # 安全检查：确保文件路径在预期的目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath('电子书')):
            return jsonify({'error': 'Invalid file path'}), 403
        
        # 检查文件是否存在
        if not os.path.isfile(file_path):
            # 如果找不到文件，尝试查找对应的文件类型
            if alt_path and os.path.isfile(alt_path):
                file_path = alt_path
            else:
                # 如果新目录中没有，尝试在有声读物目录中查找（兼容旧版本）
                old_path = os.path.join('电子书', book_name, '有声读物', filename)
                if os.path.isfile(old_path):
                    file_path = old_path
                else:
                    # 尝试查找有声读物目录中的简化文件名
                    if filename.lower().endswith('.pdf'):
                        old_alt_path = os.path.join('电子书', book_name, '有声读物', 'pdf')
                    elif filename.lower().endswith(('.m4a', '.mp3', '.wav')):
                        old_alt_path = os.path.join('电子书', book_name, '有声读物', 'm4a')
                    elif filename.lower().endswith(('.srt', '.txt')):
                        old_alt_path = os.path.join('电子书', book_name, '有声读物', 'srt')
                    else:
                        old_alt_path = None
                    
                    if old_alt_path and os.path.isfile(old_alt_path):
                        file_path = old_alt_path
                    else:
                        return jsonify({'error': 'File not found'}), 404
        
        # 返回文件
        return send_file(file_path)
    except Exception as e:
        app.logger.error('文件服务失败: %s', e)
        return jsonify({'error': f'Failed to serve file: {str(e)}'}), 500

@app.route('/api/check-file-exists/<path:book_name>/<path:filename>/<file_type>')
def check_file_exists(book_name, filename, file_type):
    """检查指定类型的文件是否存在"""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)
        
        # 安全检查：防止路径遍历攻击
        if '..' in book_name or '..' in filename:
            return jsonify({'error': '非法路径'}), 400
        
        # 根据文件类型构建不同的路径
        if file_type == 'config':
            # 配置文件路径：电子书/书名/配置信息/文件名
            file_path = os.path.join('电子书', book_name, '配置信息', filename)
        elif file_type == 'video':
            # 视频文件路径：电子书/书名/有声读物/文件名
            file_path = os.path.join('电子书', book_name, '有声读物', filename)
        else:
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # 安全检查：确保文件路径在预期的目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath('电子书')):
            return jsonify({'error': 'Invalid file path'}), 403
        
        # 添加调试日志
        app.logger.info(f'检查文件是否存在: {file_path}')
        
        # 检查文件是否存在
        if os.path.isfile(file_path):
            app.logger.info(f'文件存在: {file_path}')
            
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            # 格式化文件大小
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"
            
            # 获取文件创建时间
            create_time = os.path.getctime(file_path)
            create_time_str = datetime.fromtimestamp(create_time).strftime('%m/%d/%Y, %I:%M:%S %p')
            
            # 如果是视频文件，获取视频元数据
            metadata = {}
            if file_type == 'video':
                try:
                    # 使用ffprobe获取视频信息
                    cmd = [
                        'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
                        file_path
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    probe_data = json.loads(result.stdout)
                    
                    # 提取视频流信息
                    video_stream = None
                    for stream in probe_data.get('streams', []):
                        if stream.get('codec_type') == 'video':
                            video_stream = stream
                            break
                    
                    if video_stream:
                        # 获取分辨率
                        width = video_stream.get('width')
                        height = video_stream.get('height')
                        if width and height:
                            metadata['resolution'] = f"{width}x{height}"
                        
                        # 获取帧率
                        fps = video_stream.get('r_frame_rate')
                        if fps and '/' in fps:
                            num, den = fps.split('/')
                            try:
                                fps_value = float(num) / float(den)
                                metadata['fps'] = f"{fps_value:.2f} fps"
                            except (ValueError, ZeroDivisionError):
                                pass
                    
                    # 获取时长
                    duration = probe_data.get('format', {}).get('duration')
                    if duration:
                        try:
                            duration_sec = float(duration)
                            minutes = int(duration_sec // 60)
                            seconds = int(duration_sec % 60)
                            metadata['duration'] = f"{minutes}:{seconds:02d}"
                        except ValueError:
                            pass
                    
                    # 获取比特率
                    bitrate = probe_data.get('format', {}).get('bit_rate')
                    if bitrate:
                        try:
                            bitrate_kbps = int(bitrate) // 1000
                            metadata['bitrate'] = f"{bitrate_kbps} kbps"
                        except ValueError:
                            pass
                    
                    # 获取编码器
                    if video_stream:
                        codec = video_stream.get('codec_name')
                        if codec:
                            metadata['codec'] = codec.upper()
                    
                except (subprocess.SubprocessError, json.JSONDecodeError, KeyError) as e:
                    # 如果获取元数据失败，继续执行但不包含元数据
                    app.logger.error(f'获取视频元数据失败: {e}')
                    pass
            
            return jsonify({
                'exists': True,
                'path': file_path,
                'filename': filename,
                'create_time': create_time_str,
                'filesize': size_str,
                'metadata': metadata
            })
        else:
            app.logger.info(f'文件不存在: {file_path}')
            return jsonify({
                'exists': False,
                'path': file_path,
                'filename': filename
            })
    except Exception as e:
        app.logger.error(f'检查文件失败: {e}')
        return jsonify({'error': f'Failed to check file: {str(e)}'}), 500

@app.route('/api/check-video-exists/<path:book_name>/<filename>')
def check_video_exists(book_name, filename):
    """Check if a video file exists for the given book."""
    try:
        # 对URL编码的书名和文件名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        filename = unquote(filename)
        
        # 构建视频文件路径：电子书/书名/有声读物/文件名
        video_path = os.path.join('电子书', book_name, '有声读物', filename)
        
        # 安全检查：确保文件路径在预期的目录内
        if not os.path.abspath(video_path).startswith(os.path.abspath('电子书')):
            return jsonify({'error': 'Invalid file path'}), 403
        
        # 添加调试日志
        app.logger.info(f'检查视频文件是否存在: {video_path}')
        
        # 检查文件是否存在
        if os.path.isfile(video_path):
            app.logger.info(f'视频文件存在: {video_path}')
            
            # 获取文件大小
            file_size = os.path.getsize(video_path)
            # 格式化文件大小
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"
            
            # 获取文件创建时间
            create_time = os.path.getctime(video_path)
            create_time_str = datetime.fromtimestamp(create_time).strftime('%m/%d/%Y, %I:%M:%S %p')
            
            # 获取视频元数据（分辨率、时长等）
            video_metadata = {}
            try:
                # 使用ffprobe获取视频信息
                cmd = [
                    'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
                    video_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                probe_data = json.loads(result.stdout)
                
                # 提取视频流信息
                video_stream = None
                for stream in probe_data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        video_stream = stream
                        break
                
                if video_stream:
                    # 获取分辨率
                    width = video_stream.get('width')
                    height = video_stream.get('height')
                    if width and height:
                        video_metadata['resolution'] = f"{width}x{height}"
                    
                    # 获取帧率
                    fps = video_stream.get('r_frame_rate')
                    if fps and '/' in fps:
                        num, den = fps.split('/')
                        try:
                            fps_value = float(num) / float(den)
                            video_metadata['fps'] = f"{fps_value:.2f} fps"
                        except (ValueError, ZeroDivisionError):
                            pass
                
                # 获取时长
                duration = probe_data.get('format', {}).get('duration')
                if duration:
                    try:
                        duration_sec = float(duration)
                        minutes = int(duration_sec // 60)
                        seconds = int(duration_sec % 60)
                        video_metadata['duration'] = f"{minutes}:{seconds:02d}"
                    except ValueError:
                        pass
                
                # 获取比特率
                bitrate = probe_data.get('format', {}).get('bit_rate')
                if bitrate:
                    try:
                        bitrate_kbps = int(bitrate) // 1000
                        video_metadata['bitrate'] = f"{bitrate_kbps} kbps"
                    except ValueError:
                        pass
                
                # 获取编码器
                if video_stream:
                    codec = video_stream.get('codec_name')
                    if codec:
                        video_metadata['codec'] = codec.upper()
                
            except (subprocess.SubprocessError, json.JSONDecodeError, KeyError) as e:
                # 如果获取元数据失败，继续执行但不包含元数据
                app.logger.error(f'获取视频元数据失败: {e}')
                pass
            
            return jsonify({
                'exists': True,
                'filesize': size_str,
                'create_time': create_time_str,
                'path': video_path,
                'metadata': video_metadata
            })
        else:
            app.logger.info(f'视频文件不存在: {video_path}')
            return jsonify({'exists': False})
    except Exception as e:
        app.logger.error(f'检查视频文件失败: {e}')
        return jsonify({'error': f'Failed to check video file: {str(e)}'}), 500

@app.route('/api/open-directory/<path:book_name>')
def open_directory(book_name):
    """Open the local directory containing the generated video file."""
    # 对URL编码的书名进行解码
    from urllib.parse import unquote
    book_name = unquote(book_name)
    
    # 构建目录路径：电子书/书名/有声读物
    dir_path = os.path.join('电子书', book_name, '有声读物')
    
    # 安全检查：确保目录路径在预期的目录内
    if not os.path.abspath(dir_path).startswith(os.path.abspath('电子书')):
        return jsonify({'error': 'Invalid directory path'}), 403
    
    # 检查目录是否存在
    if not os.path.isdir(dir_path):
        return jsonify({'error': 'Directory not found'}), 404
    
    # 根据操作系统打开目录
    try:
        if sys.platform == 'darwin':  # macOS
            subprocess.run(['open', dir_path], check=True)
        elif sys.platform == 'win32':  # Windows
            subprocess.run(['explorer', dir_path], check=True)
        else:  # Linux
            subprocess.run(['xdg-open', dir_path], check=True)
        
        return jsonify({
            'status': 'success',
            'message': 'Directory opened successfully',
            'dir_path': dir_path
        })
    except Exception as e:
        return jsonify({'error': f'Failed to open directory: {str(e)}'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/audio-file/<file_key>')
def audio_file(file_key):
    """Serve audio file from memory."""
    # 检查内存中是否存在该文件
    if not hasattr(upload_file, 'memory_files'):
        return jsonify({'error': 'No files in memory'}), 404
    
    memory_files = upload_file.memory_files
    
    if file_key not in memory_files:
        return jsonify({'error': f'Audio file not found: {file_key}'}), 404
    
    file_info = memory_files[file_key]
    
    # 检查文件类型是否为音频
    if file_info['file_type'] != 'audio':
        return jsonify({'error': 'Not an audio file'}), 400
    
    # 返回音频文件内容
    return send_file(
        io.BytesIO(file_info['content']),
        mimetype='audio/mpeg',  # 通用音频MIME类型
        as_attachment=False,
        download_name=file_info['filename']
    )

@app.route('/api/save-config', methods=['POST'])
def save_config():
    """Save configuration to file."""
    data = request.get_json()
    
    # 获取书名、字幕文件名和配置数据
    book_name = data.get('book_name')
    subtitle_filename = data.get('subtitle_filename')
    config_data = data.get('config_data')
    
    if not book_name or not subtitle_filename or not config_data:
        return jsonify({'error': 'Missing book name, subtitle filename, or config data'}), 400
    
    try:
        # 处理书名，去掉括号及括号后的内容
        clean_book_name = book_name.split('(')[0].strip()
        
        # 构建配置目录路径：电子书/书名/配置信息
        config_dir = os.path.abspath(os.path.join('电子书', clean_book_name, '配置信息'))
        
        # 确保配置目录存在
        os.makedirs(config_dir, exist_ok=True)
        
        # 配置文件名统一为config.json
        config_filename = "config.json"
        config_file_path = os.path.join(config_dir, config_filename)
        
        app.logger.info('保存配置: 书名=%s, 清理后书名=%s, 配置路径=%s', 
                       book_name, clean_book_name, config_file_path)
        
        # 保存配置到文件
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': 'Configuration saved successfully',
            'config_path': config_file_path,
            'book_name': clean_book_name
        })
    except Exception as e:
        app.logger.error('保存配置失败: %s', e)
        return jsonify({'error': f'Failed to save configuration: {str(e)}'}), 500

@app.route('/api/load-config/', defaults={'book_name': '红楼梦'})
@app.route('/api/load-config/<path:book_name>')
def load_config(book_name=None):
    """Load configuration from file."""
    try:
        # 处理空值情况
        if not book_name:
            book_name = '红楼梦'
        
        # 对URL编码的书名进行解码
        from urllib.parse import unquote
        book_name = unquote(book_name)
        
        app.logger.info('开始加载配置: %s', book_name)
        
        # 获取查询参数中的字幕文件名或音频文件名
        subtitle_filename = request.args.get('subtitle_filename')
        audio_filename = request.args.get('audio_filename')
        
        # 优先从session获取上传文件路径
        file_paths = session.get('uploaded_files', []) if 'session' in globals() else []
        
        # 如果有上传文件，尝试从文件路径中提取书籍名称
        if len(file_paths) == 3:
            try:
                # 从上传的文件路径中提取公共父目录
                common_parent = os.path.commonpath(file_paths)
                app.logger.info('从上传文件提取公共父目录: %s', common_parent)
                
                # 从公共父目录中提取书籍名称
                # 例如：/Users/nayiahlu/Documents/自研项目/python项目/有声书/电子书/红楼梦
                # 我们需要提取"红楼梦"作为书名
                path_parts = common_parent.split(os.sep)
                if '电子书' in path_parts:
                    ebook_index = path_parts.index('电子书')
                    if ebook_index + 1 < len(path_parts):
                        # 使用电子书目录下的子目录作为书名
                        extracted_book_name = path_parts[ebook_index + 1]
                        app.logger.info('从文件路径提取书名: %s', extracted_book_name)
                        
                        # 构建配置目录路径：电子书/书名/配置信息
                        config_dir = os.path.abspath(os.path.join('电子书', extracted_book_name, '配置信息'))
                    else:
                        # 如果电子书目录下没有子目录，使用默认书名
                        config_dir = os.path.abspath(os.path.join('电子书', '红楼梦', '配置信息'))
                else:
                    # 如果路径中没有电子书目录，使用默认书名
                    config_dir = os.path.abspath(os.path.join('电子书', '红楼梦', '配置信息'))
            except Exception as e:
                app.logger.error('动态路径生成失败: %s', e)
                # 使用默认路径结构
                config_dir = os.path.abspath(os.path.join('电子书', '红楼梦', '配置信息'))
        else:
            # 如果没有上传文件，尝试从书名中提取主要书名
            # 检查书名中是否包含"红楼梦"关键词
            if '红楼梦' in book_name:
                # 如果书名中包含"红楼梦"，使用"红楼梦"作为书名
                config_dir = os.path.abspath(os.path.join('电子书', '红楼梦', '配置信息'))
            else:
                # 否则，去掉括号及括号后的内容
                clean_book_name = book_name.split('(')[0].strip()
                config_dir = os.path.abspath(os.path.join('电子书', clean_book_name, '配置信息'))
        
        app.logger.info('最终使用的配置目录: %s', config_dir)
        
        # 目录权限校验
        if not config_dir.startswith(os.path.abspath('电子书')):
            return jsonify({
                'status': 'error',
                'message': '非法路径访问'
            }), 403
        
        # 检查配置目录是否存在
        if not os.path.exists(config_dir):
            app.logger.info('配置目录不存在: %s', config_dir)
            return jsonify({
                'status': 'no_config',
                'message': '配置文件不存在，请先完成配置设置',
                'config_dir': config_dir
            })
        
        # 查找配置文件
        config_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
        if not config_files:
            app.logger.info('未找到配置文件: %s', config_dir)
            return jsonify({
                'status': 'no_config',
                'message': '配置文件不存在，请先完成配置设置',
                'config_dir': config_dir
            })
        
        # 确定要加载的配置文件
        config_filename = None
        if subtitle_filename:
            subtitle_name_without_ext = os.path.splitext(subtitle_filename)[0]
            config_filename = f"{subtitle_name_without_ext}.json"
        elif audio_filename:
            audio_name_without_ext = os.path.splitext(audio_filename)[0]
            config_filename = f"{audio_name_without_ext}.json"
        
        # 检查指定的配置文件是否存在
        config_file_path = None
        if config_filename and config_filename in config_files:
            config_file_path = os.path.join(config_dir, config_filename)
        else:
            # 优先加载config.json，如果不存在则加载最新配置文件
            if "config.json" in config_files:
                config_filename = "config.json"
                config_file_path = os.path.join(config_dir, config_filename)
            else:
                # 加载最新配置文件
                config_files.sort(key=lambda x: os.path.getmtime(os.path.join(config_dir, x)), reverse=True)
                config_filename = config_files[0]
                config_file_path = os.path.join(config_dir, config_filename)
        
        # 读取配置文件
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        app.logger.info('配置加载成功: %s', config_file_path)
        return jsonify({
            'status': 'success',
            'config_data': config_data,
            'config_filename': config_filename,
            'config_dir': config_dir
        })
        
    except Exception as e:
        app.logger.error('配置文件读取失败: %s', e)
        return jsonify({
            'status': 'error',
            'message': '配置文件读取失败'
        }), 500

@app.route('/api/get-uploaded-files', methods=['POST'])
def get_uploaded_files():
    """获取已上传的文件列表"""
    try:
        data = request.get_json()
        book_name = data.get('book_name', '默认书籍')
        
        app.logger.info(f'获取已上传文件列表，书名: {book_name}')
        
        # 初始化返回结果
        result = {
            'pdf': None,
            'audio': None,
            'subs': None,
            'config': None,
            'video': None
        }
        
        # 检查内存中是否有上传的文件
        if hasattr(upload_file, 'memory_files'):
            for file_key, file_info in upload_file.memory_files.items():
                if file_info['book_name'] == book_name:
                    file_type = file_info['file_type']
                    result[file_type] = {
                        'name': file_info.get('original_filename', file_info['filename']),
                        'filename': file_info['filename'],
                        'size': file_info['size'],
                        'file_key': file_key
                    }
        
        # 检查配置文件是否存在
        config_dir = os.path.join('电子书', book_name, '配置信息')
        if os.path.exists(config_dir):
            config_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
            if config_files:
                # 优先使用config.json，否则使用最新的配置文件
                if "config.json" in config_files:
                    config_filename = "config.json"
                else:
                    config_files.sort(key=lambda x: os.path.getmtime(os.path.join(config_dir, x)), reverse=True)
                    config_filename = config_files[0]
                
                config_path = os.path.join(config_dir, config_filename)
                if os.path.exists(config_path):
                    result['config'] = {
                        'name': config_filename,
                        'path': config_path,
                        'size': os.path.getsize(config_path)
                    }
        
        # 检查字幕文件是否存在
        # 首先检查是否有音频文件，如果有则查找同名字幕文件
        if result['audio']:
            # 获取音频文件名（不含扩展名）
            audio_name = os.path.splitext(result['audio']['name'])[0]
            
            # 检查字幕文件目录
            subtitle_dir = os.path.join('电子书', book_name, '字幕文件')
            if os.path.exists(subtitle_dir):
                # 查找与音频文件同名的字幕文件
                subtitle_files = [f for f in os.listdir(subtitle_dir) if f.endswith(('.srt', '.txt'))]
                matching_subtitle = None
                
                # 首先尝试精确匹配（不含扩展名）
                for subtitle_file in subtitle_files:
                    subtitle_name = os.path.splitext(subtitle_file)[0]
                    if subtitle_name == audio_name:
                        matching_subtitle = subtitle_file
                        break
                
                # 如果没有精确匹配，尝试包含音频文件名的字幕文件
                if not matching_subtitle:
                    for subtitle_file in subtitle_files:
                        if audio_name in subtitle_file:
                            matching_subtitle = subtitle_file
                            break
                
                # 如果找到匹配的字幕文件
                if matching_subtitle:
                    subtitle_path = os.path.join(subtitle_dir, matching_subtitle)
                    if os.path.exists(subtitle_path):
                        result['subs'] = {
                            'name': matching_subtitle,
                            'filename': matching_subtitle,
                            'path': subtitle_path,
                            'size': os.path.getsize(subtitle_path)
                        }
                        print(f"找到与音频文件同名的字幕文件: {matching_subtitle}")
        
        # 检查视频文件是否存在
        video_dir = os.path.join('电子书', book_name, '有声读物')
        if os.path.exists(video_dir):
            video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
            if video_files:
                # 使用最新的视频文件
                video_files.sort(key=lambda x: os.path.getmtime(os.path.join(video_dir, x)), reverse=True)
                video_filename = video_files[0]
                video_path = os.path.join(video_dir, video_filename)
                if os.path.exists(video_path):
                    result['video'] = {
                        'name': video_filename,
                        'path': video_path,
                        'size': os.path.getsize(video_path)
                    }
        
        app.logger.info(f'返回已上传文件列表: {result}')
        return jsonify(result)
    
    except Exception as e:
        app.logger.error(f'获取已上传文件列表失败: {e}')
        return jsonify({'error': f'Failed to get uploaded files: {str(e)}'}), 500

@app.route('/翻页效果/<filename>')
def serve_flip_effect(filename):
    """Serve flip effect HTML files."""
    return send_from_directory('翻页效果', filename)

@app.route('/翻页效果/js/<filename>')
def serve_flip_effect_js(filename):
    """Serve flip effect JavaScript files."""
    return send_from_directory('翻页效果/js', filename)

@app.route('/static/翻页效果/<filename>')
def serve_static_flip_effect(filename):
    """Serve flip effect files from static path."""
    return send_from_directory('翻页效果', filename)

# 缓存Whisper模型信息，有效期5分钟
_whisper_info_cache = {
    'data': None,
    'timestamp': 0
}

@app.route('/api/whisper-info', methods=['GET'])
def get_whisper_info():
    """获取Whisper模型信息"""
    import time
    
    # 检查缓存是否有效（5分钟内）
    current_time = time.time()
    if _whisper_info_cache['data'] and (current_time - _whisper_info_cache['timestamp']) < 5 * 60:
        return jsonify(_whisper_info_cache['data'])
    
    try:
        import whisper
        import torch
        import os
        from pathlib import Path
        
        # 获取Whisper版本
        whisper_version = getattr(whisper, '__version__', 'Unknown')
        
        # 检查GPU支持
        gpu_available = torch.cuda.is_available()
        gpu_device = torch.cuda.get_device_name(0) if gpu_available else None
        
        # 获取多个可能的模型缓存路径
        cache_dirs = []
        
        # 1. 默认Whisper缓存路径
        default_cache = whisper._MODELS_CACHE if hasattr(whisper, '_MODELS_CACHE') else os.path.expanduser("~/.cache/whisper")
        cache_dirs.append(('Whisper默认', default_cache))
        
        # 2. SmartSub模型路径
        smartsub_cache = os.path.expanduser("~/Library/Application Support/smartsub/whisper-models")
        if os.path.exists(smartsub_cache):
            cache_dirs.append(('SmartSub', smartsub_cache))
        
        # 3. HuggingFace缓存路径 (faster-whisper模型存储位置)
        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
        if os.path.exists(hf_cache):
            # 查找所有faster-whisper模型目录
            try:
                for item in os.listdir(hf_cache):
                    if item.startswith("models--Systran--faster-whisper-"):
                        model_dir = os.path.join(hf_cache, item)
                        if os.path.isdir(model_dir):
                            # 检查快照目录
                            snapshots_dir = os.path.join(model_dir, "snapshots")
                            if os.path.exists(snapshots_dir):
                                for snapshot in os.listdir(snapshots_dir):
                                    snapshot_path = os.path.join(snapshots_dir, snapshot)
                                    if os.path.isdir(snapshot_path):
                                        cache_dirs.append(('HuggingFace', snapshot_path))
            except Exception:
                pass
        
        # 4. 其他可能的路径
        other_paths = [
            os.path.expanduser("~/.cache/whisper-cpp"),
            os.path.expanduser("~/whisper-models"),
            "/opt/homebrew/share/whisper-models",
            "/usr/local/share/whisper-models"
        ]
        
        for path in other_paths:
            if os.path.exists(path):
                cache_dirs.append(('其他', path))
        
        # 检查已安装的模型
        installed_models = []
        
        # 使用config.py中的模型配置，不再硬编码
        for model_size, info in WHISPER_MODELS.items():
            # 使用find_model_location函数查找模型位置
            print(f'正在检查模型: {model_size.upper()}')
            model_location_info = find_model_location(model_size)
            
            if model_location_info['found']:
                print(f'✓ 找到模型 {model_size.upper()}: {model_location_info["primary_location"]["path"]}')
                if model_location_info["primary_location"]["size_mb"] > 0:
                    print(f'  文件大小: {model_location_info["primary_location"]["size_mb"]} MB')
            else:
                print(f'✗ 未找到模型 {model_size.upper()}')
            
            model_details = {
                'name': model_size,
                'parameters': info['parameters'],
                'speed': info['speed'],
                'accuracy': info['accuracy'],
                'description': info['description'],
                'recommended_use': info['recommended_use'],
                'languages': info['languages'],
                'vram_requirement': info['vram_requirement'],
                'performance_factor': info['performance_factor'],
                'status': 'installed' if model_location_info['found'] else 'not_installed',
                'locations': model_location_info['all_locations']
            }
            
            if model_location_info['found']:
                model_details['primary_location'] = model_location_info['primary_location']
            
            installed_models.append(model_details)
        
        # 检查whisper-cpp是否可用
        whisper_cpp_available = False
        whisper_cpp_path = None
        try:
            import subprocess
            result = subprocess.run(['which', 'whisper-cli'], capture_output=True, text=True)
            if result.returncode == 0:
                whisper_cpp_available = True
                whisper_cpp_path = result.stdout.strip()
        except:
            pass
        
        # 添加模型比较信息
        model_comparison = {
            'speed_ranking': ['tiny', 'base', 'large-v3-turbo', 'small', 'medium', 'large'],
            'accuracy_ranking': ['large', 'large-v3-turbo', 'medium', 'small', 'base', 'tiny'],
            'size_ranking': ['tiny', 'base', 'small', 'large-v3-turbo', 'medium', 'large'],
            'recommendations': {
                'fastest': 'tiny',
                'balanced': 'base',
                'accurate': 'large-v3-turbo',
                'most_accurate': 'large',
                'chinese_optimal': 'large-v3-turbo'
            },
            'use_cases': {
                'real_time': 'tiny',
                'daily_use': 'base',
                'professional': 'small',
                'high_quality': 'medium',
                'research': 'large',
                'chinese_content': 'large-v3-turbo'
            }
        }
        
        # 添加系统资源需求信息
        system_requirements = {
            'minimum': {
                'model': 'tiny',
                'ram': '2GB',
                'vram': '1GB',
                'storage': '100MB'
            },
            'recommended': {
                'model': 'base',
                'ram': '4GB',
                'vram': '2GB',
                'storage': '200MB'
            },
            'optimal': {
                'model': 'large-v3-turbo',
                'ram': '8GB',
                'vram': '6GB',
                'storage': '1GB'
            },
            'professional': {
                'model': 'large',
                'ram': '16GB',
                'vram': '10GB',
                'storage': '2GB'
            }
        }
        
        # 构建响应数据
        response_data = {
            'success': True,
            'whisper_version': whisper_version,
            'gpu_available': gpu_available,
            'gpu_device': gpu_device,
            'cache_dirs': cache_dirs,
            'installed_models': installed_models,
            'whisper_cpp_available': whisper_cpp_available,
            'whisper_cpp_path': whisper_cpp_path,
            'model_comparison': model_comparison,
            'system_requirements': system_requirements
        }
        
        # 更新缓存
        import time
        _whisper_info_cache['data'] = response_data
        _whisper_info_cache['timestamp'] = time.time()
        
        return jsonify(response_data)
        
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Whisper not installed'
        }), 500
    except Exception as e:
        app.logger.error(f'获取Whisper信息失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def calculate_huggingface_model_size(model_path):
    """动态计算HuggingFace模型的实际大小"""
    import os
    
    total_size = 0
    try:
        # 递归计算目录中所有文件的大小
        for root, dirs, files in os.walk(model_path):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path) and not file.endswith('.incomplete'):
                    total_size += os.path.getsize(file_path)
        
        # 转换为MB
        size_mb = round(total_size / (1024 * 1024), 1)
        return size_mb
    except Exception as e:
        print(f"计算模型大小失败: {e}")
        return 0

def find_model_location(model_size, custom_path=None):
    """查找指定模型的实际位置
    
    Args:
        model_size: 模型大小 (如 'tiny', 'base', 'small', 'medium', 'large')
        custom_path: 可选的自定义模型路径，如果提供，将优先检查此路径
    
    Returns:
        包含模型位置信息的字典
    """
    import os
    from pathlib import Path
    
    # 如果提供了自定义路径，首先检查该路径
    if custom_path and os.path.exists(custom_path):
        # 检查路径是否包含模型名称
        if model_size.lower() in custom_path.lower():
            # 计算路径大小
            if os.path.isfile(custom_path):
                file_size = os.path.getsize(custom_path)
                size_mb = round(file_size / (1024 * 1024), 1)
                return {
                    'found': True,
                    'primary_location': {
                        'cache_name': '自定义路径',
                        'path': custom_path,
                        'size': file_size,
                        'size_mb': size_mb
                    },
                    'all_locations': [{
                        'cache_name': '自定义路径',
                        'path': custom_path,
                        'size': file_size,
                        'size_mb': size_mb
                    }]
                }
            elif os.path.isdir(custom_path):
                # 对于目录，计算所有文件的总大小
                actual_size_mb = calculate_huggingface_model_size(custom_path)
                if actual_size_mb > 0:  # 确保目录中有实际文件
                    return {
                        'found': True,
                        'primary_location': {
                            'cache_name': '自定义路径',
                            'path': custom_path,
                            'size': actual_size_mb * 1024 * 1024,  # 转换为字节
                            'size_mb': actual_size_mb
                        },
                        'all_locations': [{
                            'cache_name': '自定义路径',
                            'path': custom_path,
                            'size': actual_size_mb * 1024 * 1024,  # 转换为字节
                            'size_mb': actual_size_mb
                        }]
                    }
    
    # 使用config.py中的模型文件模式，不再硬编码
    model_patterns = {}
    for model_name, model_info in WHISPER_MODELS.items():
        model_patterns[model_name] = model_info['file_patterns']
    
    # 可能的模型缓存路径
    cache_dirs = []
    
    # 1. 默认Whisper缓存路径
    try:
        import whisper
        default_cache = whisper._MODELS_CACHE if hasattr(whisper, '_MODELS_CACHE') else os.path.expanduser("~/.cache/whisper")
        cache_dirs.append(('Whisper默认', default_cache))
    except:
        cache_dirs.append(('Whisper默认', os.path.expanduser("~/.cache/whisper")))
    
    # 2. SmartSub模型路径
    smartsub_cache = os.path.expanduser("~/Library/Application Support/smartsub/whisper-models")
    if os.path.exists(smartsub_cache):
        cache_dirs.append(('SmartSub', smartsub_cache))
    
    # 3. HuggingFace缓存路径 (faster-whisper使用此路径)
    hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
    if os.path.exists(hf_cache):
        # 检查是否有faster-whisper模型
        hf_models = []
        try:
            for item in os.listdir(hf_cache):
                if item.startswith("models--Systran--faster-whisper-"):
                    model_name = item.replace("models--Systran--faster-whisper-", "")
                    model_path = os.path.join(hf_cache, item)
                    if os.path.isdir(model_path):
                        # 检查快照目录
                        snapshots_dir = os.path.join(model_path, "snapshots")
                        if os.path.exists(snapshots_dir):
                            for snapshot in os.listdir(snapshots_dir):
                                snapshot_path = os.path.join(snapshots_dir, snapshot)
                                if os.path.isdir(snapshot_path):
                                    # 检查快照目录中是否有实际模型文件
                                    # 获取目录中的文件列表
                                    files = os.listdir(snapshot_path)
                                    # 检查是否有模型相关文件
                                    has_model_files = any(file.endswith(('.bin', '.pt', '.model')) for file in files)
                                    if has_model_files:
                                        hf_models.append((f"HuggingFace ({model_name})", snapshot_path))
                                        break
        except Exception as e:
            pass  # 忽略错误，继续处理其他路径
        
        # 添加找到的HuggingFace模型路径
        cache_dirs.extend(hf_models)
    
    # 4. 其他可能的路径
    other_paths = [
        os.path.expanduser("~/.cache/whisper-cpp"),
        os.path.expanduser("~/whisper-models"),
        "/opt/homebrew/share/whisper-models",
        "/usr/local/share/whisper-models"
    ]
    
    for path in other_paths:
        if os.path.exists(path):
            cache_dirs.append(('其他', path))
    
    # 查找模型
    model_locations = []
    if model_size in model_patterns:
        for cache_name, cache_dir in cache_dirs:
            # 对于HuggingFace缓存目录，使用特殊检测逻辑
            if cache_name.startswith('HuggingFace'):
                # 从缓存名称中提取模型名称
                if '(' in cache_name and ')' in cache_name:
                    model_name = cache_name.split('(')[1].split(')')[0]
                    if model_name == model_size:
                        # 动态计算模型实际大小
                        actual_size_mb = calculate_huggingface_model_size(cache_dir)
                        if actual_size_mb > 0:  # 确保有实际文件
                            model_locations.append({
                                'cache_name': cache_name,
                                'path': cache_dir,
                                'size': actual_size_mb * 1024 * 1024,  # 转换为字节
                                'size_mb': actual_size_mb
                            })
            else:
                # 对于其他缓存目录，检查文件模式
                for pattern in model_patterns[model_size]:
                    model_path = os.path.join(cache_dir, pattern)
                    if os.path.exists(model_path):
                        file_size = os.path.getsize(model_path)
                        model_locations.append({
                            'cache_name': cache_name,
                            'path': model_path,
                            'size': file_size,
                            'size_mb': round(file_size / (1024 * 1024), 1)
                        })
    
    # 检查是否有直接位于缓存根目录的模型文件（如 base.pt, tiny.pt 等）
    if not model_locations:
        for cache_name, cache_dir in cache_dirs:
            if cache_name == 'Whisper默认':
                # 检查缓存根目录中是否有直接的模型文件
                model_file = os.path.join(cache_dir, f"{model_size}.pt")
                if os.path.exists(model_file):
                    file_size = os.path.getsize(model_file)
                    model_locations.append({
                        'cache_name': cache_name,
                        'path': model_file,
                        'size': file_size,
                        'size_mb': round(file_size / (1024 * 1024), 1)
                    })
    
    # 返回最大的模型文件作为主要位置
    if model_locations:
        primary_location = max(model_locations, key=lambda x: x['size'])
        return {
            'found': True,
            'primary_location': primary_location,
            'all_locations': model_locations
        }
    else:
        return {
            'found': False,
            'primary_location': None,
            'all_locations': []
        }

@app.route('/api/download-whisper-model', methods=['POST'])
def download_whisper_model():
    """下载指定的Whisper模型"""
    try:
        # 添加调试日志
        app.logger.info("收到下载模型请求")
        
        data = request.get_json()
        model_size = data.get('model_size', 'base')
        
        app.logger.info(f"请求下载的模型大小: {model_size}")
        
        if model_size not in WHISPER_MODELS:
            app.logger.error(f"无效的模型大小: {model_size}")
            return jsonify({'error': f'Invalid model size: {model_size}'}), 400
        
        # 检查模型是否已存在
        model_location_info = find_model_location(model_size)
        if model_location_info['found']:
            app.logger.info(f"模型 {model_size.upper()} 已存在")
            return jsonify({
                'success': True,
                'message': f'模型 {model_size.upper()} 已存在',
                'already_exists': True,
                'model_info': model_location_info
            })
        
        app.logger.info(f'开始下载模型: {model_size.upper()}')
        app.logger.info('ℹ 模型下载可能需要较长时间，请耐心等待...')
        
        # 获取设备信息
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        
        app.logger.info(f'使用设备: {device}, 计算类型: {compute_type}')
        
        # 构建模型下载链接
        model_download_url = f"https://huggingface.co/Systran/faster-whisper-{model_size}/tree/main"
        app.logger.info(f'模型下载链接: {model_download_url}')
        
        # 发送下载开始通知
        app.logger.info("发送下载开始通知")
        socketio.emit('model_download_progress', {
            'status': 'starting',
            'message': f'开始下载模型 {model_size.upper()}...',
            'model_size': model_size,
            'progress': 0,
            'device': device,
            'compute_type': compute_type,
            'download_url': model_download_url
        })
        
        # 在后台线程中下载模型
        def download_model():
            try:
                # 添加调试日志
                app.logger.info(f'后台线程开始下载模型 {model_size.upper()}...')
                app.logger.info(f'设备: {device}, 计算类型: {compute_type}')
                
                # 检查是否已被取消
                if download_id in active_downloads and active_downloads[download_id]['cancelled']:
                    app.logger.info(f'下载 {download_id} 已被取消，退出下载线程')
                    return
                
                # 发送开始下载通知
                # 使用parameters字段估算模型大小，1M参数约等于4MB
                parameters_str = WHISPER_MODELS[model_size]['parameters']
                parameters_m = int(parameters_str.replace('M', ''))
                total_size = parameters_m * 4 * 1024 * 1024  # 转换为字节
                socketio.emit('model_download_progress', {
                    'status': 'starting',
                    'message': f'开始下载模型 {model_size.upper()}...',
                    'model_size': model_size,
                    'progress': 0,
                    'downloaded_size': 0,
                    'total_size': total_size,
                    'download_speed': 0,
                    'device': device,
                    'compute_type': compute_type,
                    'download_url': model_download_url
                })
                
                # 发送初始化通知
                socketio.emit('model_download_progress', {
                    'status': 'progress',
                    'message': f'正在准备下载模型 {model_size.upper()}...',
                    'model_size': model_size,
                    'progress': 0,
                    'downloaded_size': 0,
                    'total_size': total_size,
                    'download_speed': 0,
                    'device': device,
                    'compute_type': compute_type,
                    'download_url': model_download_url
                })
                
                # 不使用local_files_only，允许下载模型
                app.logger.info("调用WhisperModel下载模型...")
                socketio.emit('model_download_progress', {
                    'status': 'progress',
                    'message': f'正在连接到模型仓库并下载模型 {model_size.upper()}...',
                    'model_size': model_size,
                    'progress': 0,  # 不显示虚拟进度
                    'downloaded_size': 0,
                    'total_size': total_size,
                    'download_speed': 0,
                    'device': device,
                    'compute_type': compute_type,
                    'download_url': model_download_url
                })
                
                # 实际下载模型，添加重试机制
                max_retries = 5  # 增加重试次数，应对服务器临时故障
                retry_delay = 10  # 增加到10秒，给服务器更多恢复时间
                model = None
                
                for attempt in range(max_retries):
                    # 检查是否已被取消
                    if download_id in active_downloads and active_downloads[download_id]['cancelled']:
                        app.logger.info(f'下载 {download_id} 已被取消，停止下载尝试')
                        return
                        
                    try:
                        app.logger.info(f'尝试下载模型 (第 {attempt + 1}/{max_retries} 次)')
                        if attempt > 0:
                            socketio.emit('model_download_progress', {
                                'status': 'progress',
                                'message': f'正在重试下载模型 {model_size.upper()} (第 {attempt + 1}/{max_retries} 次)',
                                'model_size': model_size,
                                'progress': 0,  # 不显示虚拟进度
                                'downloaded_size': 0,
                                'total_size': total_size,
                                'download_speed': 0,
                                'device': device,
                                'compute_type': compute_type,
                                'download_url': model_download_url
                            })
                            socketio.sleep(retry_delay)
                        
                        # 添加超时处理和更详细的日志
                        app.logger.info(f'开始实例化WhisperModel，模型大小: {model_size}, 设备: {device}, 计算类型: {compute_type}')
                        
                        # 使用线程和超时机制来防止下载卡住
                        import queue
                        
                        result_queue = queue.Queue()
                        error_queue = queue.Queue()
                        
                        def download_in_thread():
                            try:
                                app.logger.info(f'下载线程已启动，模型: {model_size.upper()}')
                                # 定期检查取消状态
                                while not (download_id in active_downloads and active_downloads[download_id]['cancelled']):
                                    try:
                                        model_instance = WhisperModel(model_size, device=device, compute_type=compute_type, local_files_only=False)
                                        result_queue.put(model_instance)
                                        break
                                    except Exception as e:
                                        error_queue.put(e)
                                        break
                                else:
                                    app.logger.info(f'下载 {download_id} 已被取消，退出下载线程')
                                    error_queue.put(Exception("下载已取消"))
                            except Exception as e:
                                app.logger.error(f'下载线程中发生错误: {str(e)}')
                                error_queue.put(e)
                        
                        # 启动下载线程
                        download_thread = threading.Thread(target=download_in_thread)
                        download_thread.daemon = True
                        download_thread.start()
                        
                        # 设置超时时间（根据模型大小调整，base模型给10分钟）
                        timeout_seconds = 600  # 10分钟
                        app.logger.info(f'设置下载超时时间: {timeout_seconds}秒')
                        
                        # 等待下载完成或超时
                        download_thread.join(timeout_seconds)
                        
                        # 检查是否已被取消
                        if download_id in active_downloads and active_downloads[download_id]['cancelled']:
                            app.logger.info(f'下载 {download_id} 已被取消，停止等待下载线程')
                            return
                        
                        if download_thread.is_alive():
                            # 下载超时
                            app.logger.error(f'下载超时，已等待{timeout_seconds}秒')
                            raise Exception(f"下载超时，已等待{timeout_seconds}秒")
                        
                        # 检查下载结果
                        if not error_queue.empty():
                            error = error_queue.get()
                            # 检查是否是取消错误
                            if str(error) == "下载已取消":
                                app.logger.info(f'下载 {download_id} 已被取消，停止下载')
                                return
                            raise error
                        
                        if result_queue.empty():
                            raise Exception("下载完成但未获取到模型实例")
                        
                        model = result_queue.get()
                        app.logger.info(f'成功获取模型实例: {model}')
                        break  # 下载成功，退出重试循环
                        
                    except Exception as download_error:
                        error_msg = str(download_error)
                        app.logger.error(f'下载尝试 {attempt + 1} 失败: {error_msg}')
                        
                        # 检查是否是取消错误
                        if error_msg == "下载已取消":
                            app.logger.info(f'下载 {download_id} 已被取消，停止重试')
                            return
                        
                        # 检查是否是服务器错误，这类错误可以通过重试解决
                        is_server_error = ("500 Internal Server Error" in error_msg or 
                                         "CAS service error" in error_msg or
                                         "Reqwest Error" in error_msg or
                                         "HTTP status server error" in error_msg)
                        
                        # 如果是最后一次尝试，或者不是服务器错误，则抛出异常
                        if attempt == max_retries - 1 or not is_server_error:
                            app.logger.error(f'下载失败，已达最大重试次数或遇到不可重试错误')
                            raise download_error
                        
                        # 使用指数退避策略，每次重试等待时间翻倍
                        current_retry_delay = retry_delay * (2 ** attempt)
                        app.logger.info(f'服务器错误，{current_retry_delay}秒后重试...')
                        socketio.sleep(current_retry_delay)
                        continue
                
                # 下载完成后，发送完成通知
                app.logger.info(f'模型 {model_size.upper()} 下载完成，发送通知...')
                # 使用parameters字段估算模型大小，1M参数约等于4MB
                parameters_str = WHISPER_MODELS[model_size]['parameters']
                parameters_m = int(parameters_str.replace('M', ''))
                total_size = parameters_m * 4 * 1024 * 1024  # 转换为字节
                socketio.emit('model_download_progress', {
                    'status': 'completed',
                    'message': f'模型 {model_size.upper()} 下载完成',
                    'model_size': model_size,
                    'progress': 100,
                    'downloaded_size': total_size,
                    'total_size': total_size,
                    'download_speed': 0,
                    'device': device,
                    'compute_type': compute_type,
                    'download_url': model_download_url
                })
                
                # 获取下载后的模型位置
                model_location_info = find_model_location(model_size)
                
                # 发送模型信息
                socketio.emit('model_download_progress', {
                    'status': 'info',
                    'message': f'模型位置: {model_location_info["primary_location"]["path"]}',
                    'model_size': model_size,
                    'progress': 100,
                    'downloaded_size': total_size,
                    'total_size': total_size,
                    'download_speed': 0,
                    'model_info': model_location_info
                })
                
                app.logger.info(f'✓ 模型 {model_size.upper()} 下载完成')
                app.logger.info(f'模型位置: {model_location_info["primary_location"]["path"]}')
                
                # 更新下载状态
                if download_id in active_downloads:
                    active_downloads[download_id]['status'] = 'completed'
                    app.logger.info(f'下载 {download_id} 状态更新为已完成')
                
            except Exception as e:
                # 下载失败，发送错误通知
                app.logger.error(f'模型下载失败: {str(e)}')
                app.logger.error(f'错误类型: {type(e).__name__}')
                import traceback
                app.logger.error(f'错误详情: {traceback.format_exc()}')
                
                error_msg = str(e)
                
                # 检查错误类型，提供更友好的错误信息
                is_server_error = ("500 Internal Server Error" in error_msg or 
                                 "CAS service error" in error_msg or
                                 "Reqwest Error" in error_msg or
                                 "HTTP status server error" in error_msg)
                
                is_network_error = ("Connection" in error_msg or 
                                  "Timeout" in error_msg or
                                  "Network" in error_msg)
                
                is_disk_space_error = ("No space left" in error_msg or
                                     "disk" in error_msg.lower() and "full" in error_msg.lower())
                
                # 检查是否是模型文件损坏错误
                is_model_corrupted = ("Unable to open file" in error_msg and "model.bin" in error_msg) or \
                                   "corrupted" in error_msg.lower() or \
                                   "invalid" in error_msg.lower() and "model" in error_msg.lower()
                
                # 如果模型文件损坏，尝试查找损坏的模型位置
                corrupted_model_path = None
                if is_model_corrupted:
                    try:
                        model_location_info = find_model_location(model_size)
                        if model_location_info['found']:
                            corrupted_model_path = model_location_info["primary_location"]["path"]
                            app.logger.info(f'检测到损坏的模型文件: {corrupted_model_path}')
                    except Exception as find_error:
                        app.logger.warning(f'无法查找损坏的模型位置: {str(find_error)}')
                
                # 根据错误类型提供不同的用户友好消息
                if is_server_error:
                    user_message = f"模型服务器暂时不可用，请稍后再试。错误详情: {error_msg}"
                    can_retry = True
                    error_type = 'server_error'
                elif is_network_error:
                    user_message = f"网络连接问题，请检查网络连接后重试。错误详情: {error_msg}"
                    can_retry = True
                    error_type = 'network_error'
                elif is_disk_space_error:
                    user_message = f"磁盘空间不足，请清理磁盘空间后重试。错误详情: {error_msg}"
                    can_retry = False
                    error_type = 'disk_error'
                elif is_model_corrupted:
                    user_message = f"模型文件损坏，需要删除损坏的文件并重新下载。错误详情: {error_msg}"
                    can_retry = True  # 可以重试，但需要先删除损坏的文件
                    error_type = 'model_corrupted'
                else:
                    user_message = f"模型下载失败: {error_msg}"
                    can_retry = True
                    error_type = 'unknown_error'
                
                # 构建错误响应数据
                error_data = {
                    'status': 'error',
                    'message': user_message,
                    'model_size': model_size,
                    'progress': 0,
                    'downloaded_size': 0,
                    'total_size': 0,  # 错误状态下无法获取大小，设为0
                    'download_speed': 0,
                    'error': error_msg,
                    'can_retry': can_retry,
                    'error_type': error_type
                }
                
                # 如果是模型文件损坏，添加损坏模型路径信息
                if is_model_corrupted and corrupted_model_path:
                    error_data['model_path'] = corrupted_model_path
                    error_data['requires_delete'] = True
                
                socketio.emit('model_download_progress', error_data)
                
                app.logger.error(f'模型下载失败: {str(e)}')
                
                # 更新下载状态
                if download_id in active_downloads:
                    active_downloads[download_id]['status'] = 'failed'
                    app.logger.info(f'下载 {download_id} 状态更新为失败')
        
        # 创建下载状态记录
        download_id = f"{model_size}_{int(time.time())}"
        active_downloads[download_id] = {
            'model_size': model_size,
            'status': 'downloading',
            'cancelled': False,
            'thread': None
        }
        
        # 启动后台下载线程
        import threading
        download_thread = threading.Thread(target=download_model)
        download_thread.daemon = True
        download_thread.start()
        
        # 保存线程引用
        active_downloads[download_id]['thread'] = download_thread
        
        # 添加调试日志
        app.logger.info(f'下载线程已启动，模型: {model_size.upper()}，下载ID: {download_id}')
        
        return jsonify({
            'success': True,
            'message': f'开始下载模型 {model_size.upper()}...',
            'downloading': True,
            'model_size': model_size,
            'download_id': download_id
        })
        
    except Exception as e:
        app.logger.error(f'下载模型失败: {str(e)}')
        import traceback
        app.logger.error(f'错误详情: {traceback.format_exc()}')
        return jsonify({'error': f'Failed to download model: {str(e)}'}), 500

@app.route('/api/cancel-download', methods=['POST'])
def cancel_download():
    """取消正在进行的模型下载"""
    try:
        data = request.get_json()
        download_id = data.get('download_id')
        
        if not download_id:
            # 如果没有提供download_id，取消所有正在进行的下载
            cancelled_downloads = []
            for did, download_info in list(active_downloads.items()):
                if download_info['status'] == 'downloading' and not download_info['cancelled']:
                    download_info['cancelled'] = True
                    download_info['status'] = 'cancelled'
                    cancelled_downloads.append(did)
                    
                    # 发送取消下载通知
                    socketio.emit('model_download_progress', {
                        'status': 'cancelled',
                        'message': f'模型下载已取消 ({download_info["model_size"].upper()})',
                        'model_size': download_info['model_size'],
                        'progress': 0,
                        'downloaded_size': 0,
                        'total_size': 0,
                        'download_speed': 0
                    })
            
            app.logger.info(f'用户取消了所有模型下载，共取消 {len(cancelled_downloads)} 个下载')
            
            return jsonify({
                'success': True,
                'message': f'已取消 {len(cancelled_downloads)} 个下载',
                'cancelled_downloads': cancelled_downloads
            })
        
        # 取消特定的下载
        if download_id not in active_downloads:
            return jsonify({
                'success': False,
                'message': f'下载ID {download_id} 不存在'
            }), 404
        
        download_info = active_downloads[download_id]
        
        if download_info['status'] != 'downloading':
            return jsonify({
                'success': False,
                'message': f'下载 {download_id} 不在下载状态，当前状态: {download_info["status"]}'
            }), 400
        
        if download_info['cancelled']:
            return jsonify({
                'success': False,
                'message': f'下载 {download_id} 已经被取消'
            }), 400
        
        # 标记为已取消
        download_info['cancelled'] = True
        download_info['status'] = 'cancelled'
        
        # 发送取消下载通知
        socketio.emit('model_download_progress', {
            'status': 'cancelled',
            'message': f'模型下载已取消 ({download_info["model_size"].upper()})',
            'model_size': download_info['model_size'],
            'progress': 0,
            'downloaded_size': 0,
            'total_size': 0,
            'download_speed': 0
        })
        
        app.logger.info(f'用户取消了模型下载，下载ID: {download_id}, 模型: {download_info["model_size"].upper()}')
        
        return jsonify({
            'success': True,
            'message': f'下载 {download_id} 已取消',
            'download_id': download_id,
            'model_size': download_info['model_size']
        })
        
    except Exception as e:
        app.logger.error(f'取消下载失败: {str(e)}')
        return jsonify({'error': f'Failed to cancel download: {str(e)}'}), 500

@app.route('/api/delete-whisper-model', methods=['POST'])
def delete_whisper_model():
    """删除损坏或不需要的Whisper模型"""
    try:
        data = request.get_json()
        model_size = data.get('model_size', 'base')
        custom_path = data.get('model_path')  # 获取用户提供的自定义路径
        
        if model_size not in WHISPER_MODELS:
            return jsonify({'error': f'Invalid model size: {model_size}'}), 400
        
        # 查找模型位置，优先使用自定义路径
        model_location_info = find_model_location(model_size, custom_path)
        
        if not model_location_info['found']:
            return jsonify({
                'success': False,
                'message': f'模型 {model_size.upper()} 不存在，无需删除',
                'not_found': True
            })
        
        app.logger.info(f'开始删除模型: {model_size.upper()}')
        app.logger.info(f'模型位置: {model_location_info["primary_location"]["path"]}')
        
        deleted_paths = []
        errors = []
        
        # 删除所有找到的模型文件/目录
        for location in model_location_info['all_locations']:
            path = location['path']
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    app.logger.info(f'✓ 已删除模型文件: {path}')
                    deleted_paths.append(path)
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                    app.logger.info(f'✓ 已删除模型目录: {path}')
                    deleted_paths.append(path)
                else:
                    app.logger.warning(f'⚠ 路径不存在: {path}')
            except Exception as e:
                error_msg = f'删除失败 {path}: {str(e)}'
                app.logger.error(error_msg)
                errors.append(error_msg)
        
        # 检查是否还有其他模型文件
        remaining_model_info = find_model_location(model_size)
        
        return jsonify({
            'success': len(errors) == 0,
            'message': f'模型 {model_size.upper()} 删除{"完成" if len(errors) == 0 else "部分完成"}',
            'deleted_paths': deleted_paths,
            'errors': errors,
            'model_size': model_size,
            'still_exists': remaining_model_info['found']
        })
        
    except Exception as e:
        app.logger.error(f'删除模型失败: {str(e)}')
        return jsonify({'error': f'Failed to delete model: {str(e)}'}), 500

@app.route('/api/check-model-exists', methods=['GET'])
def check_model_exists():
    """检查指定大小的Whisper模型是否存在"""
    try:
        model_size = request.args.get('model_size', 'base')
        
        if model_size not in WHISPER_MODELS:
            return jsonify({'error': f'Invalid model size: {model_size}'}), 400
        
        # 查找模型位置
        model_location_info = find_model_location(model_size)
        
        if model_location_info['found']:
            # 模型存在，返回详细信息
            primary_location = model_location_info['primary_location']
            return jsonify({
                'exists': True,
                'model_size': model_size,
                'path': primary_location['path'],
                'cache_name': primary_location['cache_name'],
                'size_mb': primary_location.get('size_mb', 0),
                'locations': model_location_info['all_locations']
            })
        else:
            # 模型不存在
            return jsonify({
                'exists': False,
                'model_size': model_size,
                'message': f'Model {model_size.upper()} not found'
            })
        
    except Exception as e:
        app.logger.error(f'检查模型存在性失败: {str(e)}')
        return jsonify({'error': f'Failed to check model: {str(e)}'}), 500

@app.route('/api/extract-subtitle-from-audio', methods=['POST'])
def extract_subtitle_from_audio():
    """从音频文件中提取字幕"""
    try:
        data = request.get_json()
        book_name = data.get('book_name', '默认书籍')
        audio_file_key = data.get('audio_file_key')
        model_size = data.get('model_size', 'base')  # 默认使用base模型
        language = data.get('language', 'zh')  # 默认中文
        
        if not audio_file_key:
            app.logger.error('缺少音频文件key参数')
            return jsonify({'error': 'Audio file key is required'}), 400
        
        app.logger.info('=' * 60)
        app.logger.info('开始字幕提取任务')
        app.logger.info(f'书名: {book_name}')
        app.logger.info(f'音频文件: {audio_file_key}')
        app.logger.info(f'选择模型: {model_size.upper()}')
        app.logger.info(f'目标语言: {language if language != "auto" else "自动检测"}')
        app.logger.info('=' * 60)
        
        # 检查内存中是否有该音频文件
        if not hasattr(upload_file, 'memory_files'):
            app.logger.error('内存中没有文件')
            return jsonify({'error': 'No files in memory'}), 404
        
        # 查找音频文件，如果找不到确切匹配，尝试匹配文件名
        app.logger.info('正在查找音频文件...')
        found_audio_key = None
        if audio_file_key in upload_file.memory_files:
            found_audio_key = audio_file_key
            app.logger.info(f'✓ 找到音频文件: {audio_file_key}')
        else:
            # 尝试匹配文件名
            for key, file_info in upload_file.memory_files.items():
                if file_info['file_type'] == 'audio' and (file_info['filename'] == audio_file_key or key.endswith(f"_{audio_file_key}") or key == audio_file_key):
                    found_audio_key = key
                    app.logger.info(f'✓ 找到匹配的音频文件: {key}')
                    break
        
        if found_audio_key is None or found_audio_key not in upload_file.memory_files:
            app.logger.error(f'✗ 未找到音频文件: {audio_file_key}')
            app.logger.error(f'可用的音频文件: {[k for k, v in upload_file.memory_files.items() if v["file_type"] == "audio"]}')
            return jsonify({'error': 'Audio file not found in memory'}), 404
        
        audio_info = upload_file.memory_files[found_audio_key]
        if audio_info['file_type'] != 'audio':
            app.logger.error(f'✗ 文件类型错误: {audio_info["file_type"]}')
            return jsonify({'error': 'Provided file is not an audio file'}), 400
        
        # 创建临时目录存储音频文件
        app.logger.info('正在准备临时文件...')
        temp_dir = tempfile.mkdtemp()
        temp_audio_path = os.path.join(temp_dir, audio_info['filename'])
        
        try:
            # 将内存中的音频文件写入临时文件
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_info['content'])
            
            file_size_mb = len(audio_info['content']) / (1024 * 1024)
            app.logger.info(f'✓ 音频文件已准备完成')
            app.logger.info(f'  文件名: {audio_info["filename"]}')
            app.logger.info(f'  文件大小: {file_size_mb:.2f} MB')
            app.logger.info(f'  临时路径: {temp_audio_path}')
            
            # 使用 faster-whisper 提取字幕
            app.logger.info('-' * 60)
            app.logger.info('正在初始化 Faster-Whisper 引擎...')
            import torch
            
            # 检查GPU支持
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            gpu_info = ""
            if device == "cuda":
                gpu_name = torch.cuda.get_device_name(0)
                gpu_info = f" ({gpu_name})"
                app.logger.info(f'✓ GPU加速可用{gpu_info}')
                app.logger.info(f'  计算类型: {compute_type}')
            else:
                app.logger.info('ℹ 使用CPU模式 (未检测到GPU)')
                app.logger.info(f'  计算类型: {compute_type}')
            
            # 检查模型是否存在
            app.logger.info(f'检查模型 {model_size.upper()} 是否存在...')
            model_location_info = find_model_location(model_size)
            
            if not model_location_info['found']:
                app.logger.warning(f'⚠ 模型 {model_size.upper()} 未找到')
                app.logger.info('ℹ 您可以选择:')
                app.logger.info('  1. 选择其他已安装的模型')
                app.logger.info('  2. 下载此模型 (需要较长时间)')
                
                # 返回模型未找到的响应，包含下载选项
                return jsonify({
                    'error': 'model_not_found',
                    'message': f'模型 {model_size.upper()} 未找到',
                    'model_size': model_size,
                    'requires_download': True,
                    'suggestion': '请选择其他已安装的模型或下载此模型'
                }), 404
            
            # 尝试使用faster-whisper加载模型，如果失败则回退到原始Whisper
            model = None
            model_info = {}
            use_original_whisper = False
            
            # 首先尝试使用faster-whisper
            if FASTER_WHISPER_AVAILABLE:
                try:
                    app.logger.info('尝试使用 Faster-Whisper 加载模型...')
                    # 对于HuggingFace模型，使用完整路径
                    model_path = model_location_info["primary_location"]["path"]
                    if model_location_info["primary_location"]["cache_name"].startswith('HuggingFace'):
                        # 使用完整路径加载模型
                        model = WhisperModel(model_path, device=device, compute_type=compute_type, local_files_only=False)
                    else:
                        # 对于其他模型，使用模型名称
                        model = WhisperModel(model_size, device=device, compute_type=compute_type, local_files_only=False)
                    
                    model_info = {
                        'name': model_size,
                        'device': device,
                        'compute_type': compute_type,
                        'engine': 'faster-whisper'
                    }
                    app.logger.info('✓ Faster-Whisper 模型加载成功')
                except Exception as model_error:
                    error_msg = str(model_error)
                    app.logger.warning(f'Faster-Whisper 加载失败: {error_msg}')
                    app.logger.info('回退到原始 Whisper 库...')
                    app.logger.info(f'模型路径信息: {model_location_info}')
                    app.logger.info(f'设备信息: {device}, 计算类型: {compute_type}')
                    use_original_whisper = True
            else:
                use_original_whisper = True
            
            # 如果faster-whisper失败或不可用，使用原始Whisper
            if use_original_whisper:
                if not WHISPER_AVAILABLE:
                    return jsonify({
                        'error': 'no_whisper_library',
                        'message': '没有可用的Whisper库',
                        'details': 'faster-whisper和原始whisper都不可用'
                    }), 500
                
                try:
                    app.logger.info('使用原始 Whisper 加载模型...')
                    # 设置模型目录
                    model_dir = os.path.expanduser('~/.cache/whisper')
                    os.makedirs(model_dir, exist_ok=True)
                    
                    # 使用原始Whisper加载模型
                    model = whisper.load_model(model_size, download_root=model_dir)
                    
                    model_info = {
                        'name': model_size,
                        'device': 'cpu',  # 原始Whisper默认使用CPU
                        'engine': 'whisper'
                    }
                    app.logger.info('✓ 原始 Whisper 模型加载成功')
                except Exception as whisper_error:
                    app.logger.error(f'原始 Whisper 加载也失败: {str(whisper_error)}')
                    app.logger.error(f'模型大小: {model_size}')
                    app.logger.error(f'模型目录: {model_dir}')

                    # 检查模型文件是否存在
                    model_file_path = os.path.join(model_dir, f"{model_size}.pt")
                    if os.path.exists(model_file_path):
                        app.logger.info(f'模型文件存在: {model_file_path}, 大小: {os.path.getsize(model_file_path)} bytes')
                    else:
                        app.logger.info(f'模型文件不存在: {model_file_path}')

                    return jsonify({
                        'error': 'model_load_failed',
                        'message': f'无法加载模型 {model_size.upper()}',
                        'suggestions': [
                            '尝试重新下载模型',
                            '检查磁盘空间是否充足',
                            '确认网络连接正常',
                            '尝试使用不同的模型大小'
                        ],
                        'faster_whisper_error': str(model_error) if 'model_error' in locals() else 'N/A',
                        'whisper_error': str(whisper_error),
                        'model_info': {
                            'size': model_size,
                            'directory': model_dir,
                            'file_exists': os.path.exists(model_file_path)
                        }
                    }), 500
            
            app.logger.info(f'✓ 模型加载完成')
            app.logger.info(f'  引擎: {model_info["engine"]}')
            app.logger.info(f'  运行设备: {model_info["device"].upper()}{gpu_info}')
            if 'compute_type' in model_info:
                app.logger.info(f'  计算类型: {model_info["compute_type"]}')
            
            # 记录模型性能信息
            performance_info = {
                'tiny': {'speed': '非常快', 'accuracy': '低', 'description': '适合快速测试'},
                'base': {'speed': '快', 'accuracy': '中等', 'description': '适合日常使用'},
                'small': {'speed': '中等', 'accuracy': '高', 'description': '适合高质量转录'},
                'medium': {'speed': '慢', 'accuracy': '很高', 'description': '适合专业级应用'},
                'large': {'speed': '非常慢', 'accuracy': '最高', 'description': '适合最高精度要求'},
                'large-v3-turbo': {'speed': '中等', 'accuracy': '很高', 'description': '高精度与速度平衡的最佳选择'}
            }
            
            if model_size in performance_info:
                perf = performance_info[model_size]
                app.logger.info(f'  模型特点: {perf["description"]}')
                app.logger.info(f'  处理速度: {perf["speed"]} | 识别精度: {perf["accuracy"]}')
            
            # 转录音频
            app.logger.info('-' * 60)
            app.logger.info('开始转录音频...')
            app.logger.info(f'  目标语言: {language if language != "auto" else "自动检测"}')
            socketio.sleep(0)  # 确保日志立即发送
            
            # 根据模型类型使用不同的转录方法
            segments_list = []
            detected_language = language if language != 'auto' else 'zh'  # 默认中文
            
            if model_info['engine'] == 'faster-whisper':
                # faster-whisper 转录
                app.logger.info('使用 Faster-Whisper 进行转录...')
                
                # 设置转录参数
                transcribe_options = {
                    'beam_size': 5,
                    'vad_filter': True,  # 启用语音活动检测
                    'vad_parameters': dict(min_silence_duration_ms=500)
                }
                
                # 如果不是自动检测语言，则指定语言
                if language != 'auto':
                    transcribe_options['language'] = language
                
                app.logger.info('正在处理音频，这可能需要一些时间...')
                socketio.sleep(0)  # 确保日志立即发送
                
                # faster-whisper 返回的是生成器，需要转换为列表
                segments, info = model.transcribe(temp_audio_path, **transcribe_options)
                
                # 记录检测到的语言
                detected_language = info.language
                language_names = {
                    'zh': '中文', 'en': '英文', 'ja': '日文', 'ko': '韩文',
                    'es': '西班牙文', 'fr': '法文', 'de': '德文'
                }
                detected_language_name = language_names.get(detected_language, detected_language)
                
                app.logger.info(f'ℹ 检测到的语言: {detected_language_name} ({detected_language})')
                app.logger.info(f'ℹ 语言概率: {info.language_probability:.2%}')
                
                # 将生成器转换为列表并记录进度
                app.logger.info('正在处理音频片段...')
                for i, segment in enumerate(segments):
                    segments_list.append(segment)
                    if (i + 1) % 10 == 0:
                        app.logger.info(f'  已处理 {i + 1} 个片段...')
                        socketio.sleep(0)
            
            else:
                # 原始 Whisper 转录
                app.logger.info('使用原始 Whisper 进行转录...')
                
                # 设置转录参数
                transcribe_options = {}
                if language != 'auto':
                    transcribe_options['language'] = language
                
                app.logger.info('正在处理音频，这可能需要一些时间...')
                socketio.sleep(0)  # 确保日志立即发送
                
                # 原始 Whisper 转录
                result = model.transcribe(temp_audio_path, **transcribe_options)
                
                # 记录检测到的语言
                detected_language = result.get('language', 'zh')
                language_names = {
                    'zh': '中文', 'en': '英文', 'ja': '日文', 'ko': '韩文',
                    'es': '西班牙文', 'fr': '法文', 'de': '德文'
                }
                detected_language_name = language_names.get(detected_language, detected_language)
                
                app.logger.info(f'ℹ 检测到的语言: {detected_language_name} ({detected_language})')
                
                # 将原始 Whisper 的结果转换为统一格式
                app.logger.info('正在处理音频片段...')
                for i, segment in enumerate(result.get('segments', [])):
                    # 创建一个兼容的对象，具有与faster-whisper相同的属性
                    class WhisperSegment:
                        def __init__(self, start, end, text):
                            self.start = start
                            self.end = end
                            self.text = text
                    
                    segments_list.append(WhisperSegment(
                        start=segment.get('start', 0),
                        end=segment.get('end', 0),
                        text=segment.get('text', '')
                    ))
                    
                    if (i + 1) % 10 == 0:
                        app.logger.info(f'  已处理 {i + 1} 个片段...')
                        socketio.sleep(0)
            
            app.logger.info(f'✓ 音频转录完成')
            app.logger.info(f'  总片段数: {len(segments_list)}')
            
            # 生成SRT格式的字幕
            app.logger.info('-' * 60)
            app.logger.info('正在生成字幕文件...')
            subtitle_content = ""
            segment_count = len(segments_list)
            
            for i, segment in enumerate(segments_list):
                start_time = format_time(segment.start)
                end_time = format_time(segment.end)
                text = segment.text.strip()
                
                subtitle_content += f"{i + 1}\n"
                subtitle_content += f"{start_time} --> {end_time}\n"
                subtitle_content += f"{text}\n\n"
                
                # 每处理10个片段输出一次进度
                if (i + 1) % 10 == 0 or (i + 1) == segment_count:
                    progress = int((i + 1) / segment_count * 100)
                    app.logger.info(f'  生成进度: {i + 1}/{segment_count} ({progress}%)')
                    socketio.sleep(0)  # 确保日志立即发送
            
            app.logger.info(f'✓ 字幕文件生成完成')
            app.logger.info(f'  字幕片段数: {segment_count}')
            
            # 生成字幕文件名 - 直接使用音频文件名，仅后缀不同
            # 使用原始文件名而不是经过secure_filename处理的文件名
            # 从音频文件信息中获取原始文件名
            original_filename = audio_info.get('original_filename', audio_info['filename'])
            audio_name_without_ext = os.path.splitext(original_filename)[0]
            subtitle_filename = f"{audio_name_without_ext}.srt"
            
            app.logger.info(f'音频文件键: {found_audio_key}')
            app.logger.info(f'处理后文件名: {audio_info["filename"]}')
            app.logger.info(f'原始文件名: {original_filename}')
            app.logger.info(f'生成的字幕文件名: {subtitle_filename}')
            
            # 将字幕内容存储到内存中
            subtitle_bytes = subtitle_content.encode('utf-8')
            subtitle_key = f"{book_name}_{subtitle_filename}"
            
            # 创建字幕文件目录路径 - 使用规定的字幕文件存放目录
            subtitle_dir = os.path.join(os.getcwd(), "电子书", book_name, "字幕文件")
            os.makedirs(subtitle_dir, exist_ok=True)
            subtitle_file_path = os.path.join(subtitle_dir, subtitle_filename)
            
            # 将字幕文件保存到磁盘 - 直接使用音频文件名和规定的目录
            with open(subtitle_file_path, 'w', encoding='utf-8') as f:
                f.write(subtitle_content)
            
            app.logger.info(f'字幕文件已保存到: {subtitle_file_path}')
            app.logger.info(f'字幕文件名基于音频文件名: {audio_info["filename"]} -> {subtitle_filename}')
            
            # 只保存与音频文件名匹配的字幕文件，确保字幕文件名与音频文件名保持一致
            # 不再保存固定名称的兼容性文件，避免硬编码文件名
            
            if not hasattr(upload_file, 'memory_files'):
                upload_file.memory_files = {}
            
            # 检查是否已存在同名字幕文件
            existing_subtitle = None
            if subtitle_key in upload_file.memory_files:
                existing_subtitle = upload_file.memory_files[subtitle_key]
                app.logger.info(f'⚠ 检测到同名字幕文件已存在: {subtitle_filename}')
                app.logger.info(f'  现有文件大小: {existing_subtitle["size"] / 1024:.2f} KB')
                app.logger.info(f'  新文件大小: {len(subtitle_bytes) / 1024:.2f} KB')
            
            upload_file.memory_files[subtitle_key] = {
                'content': subtitle_bytes,
                'filename': subtitle_filename,
                'file_type': 'subs',
                'book_name': book_name,
                'size': len(subtitle_bytes),
                'file_path': subtitle_file_path,  # 添加文件路径信息
                'overwritten': existing_subtitle is not None  # 标记是否覆盖了现有文件
            }
            
            subtitle_size_kb = len(subtitle_bytes) / 1024
            app.logger.info('-' * 60)
            app.logger.info('字幕提取任务完成！')
            app.logger.info(f'  输出文件: {subtitle_filename}')
            app.logger.info(f'  保存路径: {subtitle_file_path}')
            app.logger.info(f'  文件大小: {subtitle_size_kb:.2f} KB')
            app.logger.info(f'  字幕片段: {segment_count} 个')
            app.logger.info(f'  使用模型: {model_size.upper()}')
            app.logger.info(f'  运行设备: {model_info["device"].upper()}{gpu_info}')
            app.logger.info(f'  检测语言: {detected_language_name}')
            app.logger.info('=' * 60)
            
            # 准备返回的模型信息
            response_model_info = model_info.copy()
            response_model_info['performance'] = performance_info.get(model_size, {})
            
            return jsonify({
                'success': True,
                'message': '字幕提取成功' + (' (已覆盖同名文件)' if existing_subtitle else ''),
                'subtitle_filename': subtitle_filename,
                'subtitle_key': subtitle_key,
                'subtitle_path': subtitle_file_path,  # 添加文件路径
                'subtitle_content': subtitle_content,
                'size': len(subtitle_bytes),
                'model_info': response_model_info,
                'detected_language': detected_language,
                'segment_count': segment_count,
                'overwritten': existing_subtitle is not None
            })
            
        finally:
            # 清理临时文件
            app.logger.info('正在清理临时文件...')
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            os.rmdir(temp_dir)
            app.logger.info('✓ 临时文件已清理')
            
    except Exception as e:
        app.logger.error('=' * 60)
        app.logger.error('字幕提取失败！')
        app.logger.error(f'错误信息: {str(e)}')
        app.logger.error('=' * 60)
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Failed to extract subtitle from audio: {str(e)}'}), 500

@app.route('/api/whisper-model-info', methods=['POST'])
def get_whisper_model_info():
    """获取Whisper模型信息"""
    try:
        data = request.get_json()
        model_size = data.get('model_size', 'base')  # 默认使用base模型
        
        app.logger.info(f'获取模型信息: 模型={model_size}')
        
        # 查找模型位置
        model_location_info = find_model_location(model_size)
        
        # 准备模型信息
        model_info = {
            'model_name': model_size,
            'device': 'cuda' if torch.cuda.is_available() else 'cpu'
        }
        
        # 添加模型位置信息
        if model_location_info['found']:
            model_info['model_location'] = model_location_info['primary_location']['path']
            model_info['model_source'] = model_location_info['primary_location']['cache_name']
            model_info['model_size_mb'] = model_location_info['primary_location']['size_mb']
        else:
            model_info['model_location'] = '自动下载'
            model_info['model_source'] = 'OpenAI官方'
            model_info['model_size_mb'] = '未知'
        
        # 添加模型参数信息 - 从配置中获取
        if model_size in WHISPER_MODELS:
            model_info['parameters'] = WHISPER_MODELS[model_size]['parameters']
        
        # 添加性能信息 - 从配置中获取
        if model_size in WHISPER_MODELS:
            model_config = WHISPER_MODELS[model_size]
            model_info['performance'] = f"{model_config['speed']}速度, {model_config['accuracy']}精度 - {model_config['description']}"
        
        app.logger.info(f'返回模型信息: {model_info}')
        
        return jsonify({
            'success': True,
            'model_info': model_info
        })
        
    except Exception as e:
        app.logger.error(f'获取模型信息失败: {e}')
        return jsonify({'error': f'Failed to get model info: {str(e)}'}), 500

@app.route('/api/extract-subtitle-whisper-cpp', methods=['POST'])
def extract_subtitle_whisper_cpp():
    """使用whisper-cpp从音频文件中提取字幕"""
    try:
        import subprocess
        import os
        
        data = request.get_json()
        book_name = data.get('book_name', '默认书籍')
        audio_file_key = data.get('audio_file_key')
        model_size = data.get('model_size', 'base')
        language = data.get('language', 'zh')
        
        if not audio_file_key:
            return jsonify({'error': 'Audio file key is required'}), 400
        
        app.logger.info(f'使用whisper-cpp提取字幕: 书名={book_name}, 模型={model_size}, 语言={language}')
        
        # 检查whisper-cpp是否可用
        try:
            result = subprocess.run(['which', 'whisper-cli'], capture_output=True, text=True)
            if result.returncode != 0:
                return jsonify({'error': 'whisper-cpp not available'}), 500
            whisper_cli_path = result.stdout.strip()
            app.logger.info(f'找到whisper-cli: {whisper_cli_path}')
        except Exception as e:
            return jsonify({'error': f'whisper-cpp check failed: {str(e)}'}), 500
        
        # 检查内存中是否有该音频文件
        if not hasattr(upload_file, 'memory_files'):
            return jsonify({'error': 'No files in memory'}), 404
        
        # 查找音频文件
        found_audio_key = None
        if audio_file_key in upload_file.memory_files:
            found_audio_key = audio_file_key
        else:
            for key, file_info in upload_file.memory_files.items():
                if file_info['file_type'] == 'audio' and (file_info['filename'] == audio_file_key or key.endswith(f"_{audio_file_key}") or key == audio_file_key):
                    found_audio_key = key
                    break
        
        if found_audio_key is None:
            return jsonify({'error': 'Audio file not found in memory'}), 404
        
        audio_info = upload_file.memory_files[found_audio_key]
        if audio_info['file_type'] != 'audio':
            return jsonify({'error': 'Provided file is not an audio file'}), 400
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_audio_path = os.path.join(temp_dir, audio_info['filename'])
        
        try:
            # 写入音频文件
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_info['content'])
            
            app.logger.info(f'音频文件已写入: {temp_audio_path}')
            
            # 查找合适的模型文件
            model_path = find_whisper_cpp_model(model_size)
            if not model_path:
                return jsonify({'error': f'Model {model_size} not found for whisper-cpp'}), 404
            
            app.logger.info(f'使用模型文件: {model_path}')
            
            # 构建whisper-cpp命令
            output_base = os.path.join(temp_dir, 'output')
            cmd = [
                'whisper-cli',
                '-m', model_path,
                '-f', temp_audio_path,
                '-l', language if language != 'auto' else 'zh',
                '-osrt',
                '-of', output_base  # whisper-cpp会自动添加.srt后缀
            ]
            
            app.logger.info(f'执行命令: {" ".join(cmd)}')
            
            # 执行whisper-cpp并实时发送输出到前端
            app.logger.info('开始执行whisper-cpp，实时输出字幕内容...')
            
            # 使用Popen实时处理输出
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 实时处理stdout和stderr
            import threading
            from queue import Queue
            
            def enqueue_output(out, queue):
                for line in iter(out.readline, ''):
                    queue.put(line)
                out.close()
            
            # 创建线程来读取stdout和stderr
            stdout_queue = Queue()
            stderr_queue = Queue()
            stdout_thread = threading.Thread(target=enqueue_output, args=(process.stdout, stdout_queue))
            stderr_thread = threading.Thread(target=enqueue_output, args=(process.stderr, stderr_queue))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # 实时处理输出
            stdout_lines = []
            stderr_lines = []
            
            while process.poll() is None:
                # 处理stdout
                try:
                    while True:
                        line = stdout_queue.get_nowait()
                        stdout_lines.append(line)
                        # 发送实时字幕内容到前端
                        if line.strip():
                            app.logger.info(f'字幕: {line.strip()}')
                            # 强制刷新事件队列，确保消息立即发送
                            socketio.sleep(0)
                except:
                    pass
                
                # 处理stderr
                try:
                    while True:
                        line = stderr_queue.get_nowait()
                        stderr_lines.append(line)
                        app.logger.warning(f'whisper-cpp警告: {line.strip()}')
                        # 强制刷新事件队列，确保消息立即发送
                        socketio.sleep(0)
                except:
                    pass
                
                time.sleep(0.05)  # 减少延迟，提高实时性
            
            # 等待线程完成
            stdout_thread.join()
            stderr_thread.join()
            
            # 获取剩余的输出
            try:
                while True:
                    line = stdout_queue.get_nowait()
                    stdout_lines.append(line)
                    if line.strip():
                        app.logger.info(f'字幕: {line.strip()}')
                        # 强制刷新事件队列，确保消息立即发送
                        socketio.sleep(0)
            except:
                pass
                
            try:
                while True:
                    line = stderr_queue.get_nowait()
                    stderr_lines.append(line)
                    app.logger.warning(f'whisper-cpp警告: {line.strip()}')
                    # 强制刷新事件队列，确保消息立即发送
                    socketio.sleep(0)
            except:
                pass
            
            # 检查执行结果
            if process.returncode != 0:
                stderr_output = ''.join(stderr_lines)
                app.logger.error(f'whisper-cpp执行失败: {stderr_output}')
                return jsonify({'error': f'whisper-cpp failed: {stderr_output}'}), 500
            
            stdout_output = ''.join(stdout_lines)
            app.logger.info(f'whisper-cpp执行成功')
            
            # 读取生成的字幕文件
            output_srt = output_base + '.srt'
            if os.path.exists(output_srt):
                with open(output_srt, 'r', encoding='utf-8') as f:
                    subtitle_content = f.read()
            else:
                # 尝试其他可能的输出文件名
                possible_outputs = [
                    os.path.join(temp_dir, 'output.srt'),
                    os.path.join(temp_dir, f'{os.path.basename(temp_audio_path)}.srt'),
                    temp_audio_path.replace(os.path.splitext(temp_audio_path)[1], '.srt')
                ]
                
                subtitle_content = None
                for possible_output in possible_outputs:
                    if os.path.exists(possible_output):
                        with open(possible_output, 'r', encoding='utf-8') as f:
                            subtitle_content = f.read()
                        app.logger.info(f'找到字幕文件: {possible_output}')
                        break
                
                if subtitle_content is None:
                    app.logger.error(f'未找到字幕文件，检查的路径: {[output_srt] + possible_outputs}')
                    return jsonify({'error': 'Subtitle file not generated'}), 500
            
            # 计算字幕片段数量
            segment_count = len([line for line in subtitle_content.split('\n') if line.strip().isdigit()])
            
            # 生成字幕文件名 - 直接使用音频文件名，仅后缀不同
            audio_name_without_ext = os.path.splitext(audio_info['filename'])[0]
            subtitle_filename = f"{audio_name_without_ext}_whisper_cpp.srt"
            
            # 创建字幕文件保存路径 - 使用规定的字幕文件存放目录
            subtitle_dir = os.path.join("电子书", book_name, "字幕文件")
            os.makedirs(subtitle_dir, exist_ok=True)
            subtitle_file_path = os.path.join(subtitle_dir, subtitle_filename)
            
            # 将字幕内容保存到文件系统 - 直接使用音频文件名和规定的目录
            with open(subtitle_file_path, 'w', encoding='utf-8') as f:
                f.write(subtitle_content)
            
            app.logger.info(f'字幕文件已保存到: {subtitle_file_path}')
            app.logger.info(f'字幕文件名基于音频文件名: {audio_info["filename"]} -> {subtitle_filename}')
            
            # 存储到内存
            subtitle_bytes = subtitle_content.encode('utf-8')
            subtitle_key = f"{book_name}_{subtitle_filename}"
            
            if not hasattr(upload_file, 'memory_files'):
                upload_file.memory_files = {}
            
            upload_file.memory_files[subtitle_key] = {
                'content': subtitle_bytes,
                'filename': subtitle_filename,
                'file_type': 'subs',
                'book_name': book_name,
                'size': len(subtitle_bytes),
                'file_path': subtitle_file_path  # 添加文件路径信息
            }
            
            app.logger.info(f'字幕提取完成: {subtitle_filename}, 使用whisper-cpp, 模型: {model_path}')
            app.logger.info(f'保存路径: {subtitle_file_path}')
            
            return jsonify({
                'success': True,
                'message': '字幕提取成功 (whisper-cpp)',
                'subtitle_filename': subtitle_filename,
                'subtitle_key': subtitle_key,
                'subtitle_content': subtitle_content,
                'subtitle_path': subtitle_file_path,  # 添加保存路径
                'size': len(subtitle_bytes),
                'model_info': {
                    'name': model_size,
                    'engine': 'whisper-cpp',
                    'model_path': model_path,
                    'device': 'cpu'
                },
                'segment_count': segment_count,
                'detected_language': language
            })
            
        finally:
            # 清理临时文件
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
    except Exception as e:
        app.logger.error(f'whisper-cpp字幕提取失败: {e}')
        return jsonify({'error': f'Failed to extract subtitle with whisper-cpp: {str(e)}'}), 500

def find_whisper_cpp_model(model_size):
    """查找whisper-cpp兼容的模型文件"""
    import os
    
    app.logger.info(f'查找whisper-cpp模型: {model_size}')
    
    # 可能的模型路径
    search_paths = [
        os.path.expanduser("~/Library/Application Support/smartsub/whisper-models"),
        os.path.expanduser("~/.cache/whisper"),
        os.path.expanduser("~/whisper-models"),
        "/opt/homebrew/share/whisper-models",
        "/usr/local/share/whisper-models"
    ]
    
    # 模型文件名模式 - 优先匹配更具体的模式
    model_patterns = {
        'tiny': ['ggml-tiny-q8_0.bin', 'ggml-tiny.bin'],
        'base': ['ggml-base-q8_0.bin', 'ggml-base.bin'],
        'small': ['ggml-small-q8_0.bin', 'ggml-small.bin'],
        'medium': ['ggml-medium-q8_0.bin', 'ggml-medium.bin'],
        'large': [
            'ggml-large-v3-turbo-q8_0.bin',  # 你的模型文件
            'ggml-large-v3-q8_0.bin',
            'ggml-large-v3.bin',
            'ggml-large-q8_0.bin',
            'ggml-large.bin'
        ]
    }
    
    patterns = model_patterns.get(model_size, [])
    app.logger.info(f'搜索模式: {patterns}')
    
    for search_path in search_paths:
        app.logger.info(f'搜索路径: {search_path}')
        if not os.path.exists(search_path):
            app.logger.info(f'路径不存在: {search_path}')
            continue
            
        # 列出目录中的所有文件用于调试
        try:
            files = os.listdir(search_path)
            app.logger.info(f'目录 {search_path} 中的文件: {files}')
        except Exception as e:
            app.logger.warning(f'无法列出目录 {search_path}: {e}')
            continue
            
        for pattern in patterns:
            model_path = os.path.join(search_path, pattern)
            app.logger.info(f'检查模型文件: {model_path}')
            if os.path.exists(model_path):
                file_size = os.path.getsize(model_path)
                app.logger.info(f'找到模型文件: {model_path}, 大小: {file_size / (1024*1024):.1f} MB')
                return model_path
    
    app.logger.warning(f'未找到 {model_size} 模型的whisper-cpp文件')
    return None

def format_time(seconds):
    """将秒数转换为SRT时间格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60
    milliseconds = int(round(seconds * 1000))
    seconds = int(seconds)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

@app.teardown_appcontext
def cleanup_context(error):
    """Cleanup function called after each request."""
    # Periodically clean up old files
    if hasattr(app, '_last_cleanup'):
        if time.time() - app._last_cleanup > 3600:  # 1 hour
            cleanup_old_files()
            app._last_cleanup = time.time()
    else:
        app._last_cleanup = time.time()


def get_subtitle_files(book_name):
    """
    获取指定书籍的所有字幕文件列表
    """
    try:
        if not book_name or book_name.strip() == '':
            return jsonify({'error': '书名不能为空'}), 400
        
        book_name = book_name.strip()
        subtitle_dir = os.path.join("电子书", book_name, "字幕文件")
        
        # 检查目录是否存在
        if not os.path.exists(subtitle_dir):
            return jsonify({
                'success': True,
                'message': '字幕目录不存在',
                'subtitle_files': []
            })
        
        # 获取目录中的所有字幕文件
        subtitle_files = []
        
        # 支持的字幕文件扩展名
        subtitle_extensions = ['.srt', '.vtt', '.ass', '.ssa']
        
        try:
            for file in os.listdir(subtitle_dir):
                file_path = os.path.join(subtitle_dir, file)
                if os.path.isfile(file_path):
                    # 检查文件扩展名
                    _, ext = os.path.splitext(file)
                    if ext.lower() in subtitle_extensions:
                        # 获取文件信息
                        stat = os.stat(file_path)
                        subtitle_files.append({
                            'name': file,
                            'size': stat.st_size,
                            'modified': stat.st_mtime
                        })
        except Exception as e:
            app.logger.error(f'读取字幕目录失败: {e}')
            return jsonify({'error': f'读取字幕目录失败: {str(e)}'}), 500
        
        # 按文件名排序
        subtitle_files.sort(key=lambda x: x['name'])
        
        # 使用Response对象直接返回JSON，确保中文字符不被编码为Unicode转义序列
        response_data = {
            'success': True,
            'book_name': book_name,
            'subtitle_files': subtitle_files,
            'count': len(subtitle_files)
        }
        return Response(json.dumps(response_data, ensure_ascii=False), mimetype='application/json')
        
    except Exception as e:
        app.logger.error(f'获取字幕文件列表失败: {e}')
        return jsonify({'error': f'获取失败: {str(e)}'}), 500

@app.route('/api/get-subtitle-content', methods=['GET'])
def get_subtitle_content():
    """
    获取生成的字幕文本内容
    """
    try:
        book_name = request.args.get('book_name', '').strip()
        subtitle_filename = request.args.get('subtitle_filename', '').strip()
        
        if book_name == '':
            return jsonify({'error': '书名不能为空'}), 400
            
        if subtitle_filename == '':
            return jsonify({'error': '字幕文件名不能为空'}), 400
        
        # 查找字幕文件
        subtitle_key = f"{book_name}_{subtitle_filename}"
        
        if hasattr(upload_file, 'memory_files') and subtitle_key in upload_file.memory_files:
            subtitle_data = upload_file.memory_files[subtitle_key]
            subtitle_content = subtitle_data['content'].decode('utf-8')
            
            # 使用Response对象直接返回JSON，确保中文字符不被编码为Unicode转义序列
            response_data = {
                'success': True,
                'subtitle_content': subtitle_content,
                'filename': subtitle_filename,
                'size': len(subtitle_content.encode('utf-8'))
            }
            return Response(json.dumps(response_data, ensure_ascii=False), mimetype='application/json')
        else:
            # 尝试从文件系统读取
            subtitle_path = os.path.join("电子书", book_name, "字幕文件", subtitle_filename)
            
            if os.path.exists(subtitle_path):
                with open(subtitle_path, 'r', encoding='utf-8') as f:
                    subtitle_content = f.read()
                
                # 使用Response对象直接返回JSON，确保中文字符不被编码为Unicode转义序列
                response_data = {
                    'success': True,
                    'subtitle_content': subtitle_content,
                    'filename': subtitle_filename,
                    'size': len(subtitle_content.encode('utf-8')),
                    'path': subtitle_path
                }
                return Response(json.dumps(response_data, ensure_ascii=False), mimetype='application/json')
            else:
                return jsonify({'error': '找不到指定的字幕文件'}), 404
                
    except Exception as e:
        app.logger.error(f'获取字幕内容失败: {e}')
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


# ==================== DeepSeek API 端点 ====================

@app.route('/api/deepseek-config', methods=['GET'])
def get_deepseek_config():
    """获取DeepSeek API配置信息"""
    try:
        client = get_deepseek_client()
        api_info = client.get_api_info()
        
        # 获取系统配置的API密钥
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if api_key:
            api_info['api_key'] = api_key

        return jsonify({
            'success': True,
            'config': api_info
        })

    except Exception as e:
        app.logger.error(f'获取DeepSeek配置失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/deepseek-test', methods=['POST'])
def test_deepseek_connection():
    """测试DeepSeek API连接"""
    try:
        data = request.get_json()
        # 支持两种参数名以兼容前端
        api_key = data.get('api_key', '').strip() or data.get('api', '').strip()

        # 如果提供了API密钥，临时设置
        if api_key:
            client = get_deepseek_client(api_key)
        else:
            client = get_deepseek_client()

        # 测试连接
        result = client.test_connection()

        return jsonify(result)

    except Exception as e:
        app.logger.error(f'DeepSeek连接测试失败: {e}')
        return jsonify({
            'success': False,
            'message': f'连接测试失败: {str(e)}'
        }), 500


@app.route('/api/deepseek-correct-subtitle', methods=['POST'])
def correct_subtitle_with_deepseek():
    """使用DeepSeek API校正字幕"""
    try:
        data = request.get_json()

        # 获取参数 - 支持两种参数名以兼容前端
        api_key = data.get('api_key', '').strip() or data.get('api', '').strip()
        subtitle_text = data.get('subtitle_text', '').strip()
        original_text = data.get('original_text', '').strip()
        enable_deepthink = data.get('enable_deepthink', True)
        book_name = data.get('book_name', '').strip()
        batch_size = data.get('batch_size', 50)  # 默认50条/批

        # 验证必需参数
        if not subtitle_text:
            return jsonify({
                'success': False,
                'error': '字幕文本不能为空'
            }), 400

        if not original_text:
            return jsonify({
                'success': False,
                'error': '原文文本不能为空'
            }), 400

        if not api_key:
            # 如果请求中没有API密钥，尝试从环境变量获取
            api_key = os.getenv('DEEPSEEK_API_KEY')
            
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API密钥不能为空'
            }), 400

        app.logger.info(f'开始DeepSeek字幕校正: 书名={book_name}, 字幕长度={len(subtitle_text)}, 原文长度={len(original_text)}, DeepThink={enable_deepthink}, 每批={batch_size}条')

        # 获取DeepSeek客户端
        client = get_deepseek_client(api_key)

        # 执行字幕校正
        result = client.correct_subtitle(
            subtitle_text=subtitle_text,
            original_text=original_text,
            enable_deepthink=enable_deepthink,
            batch_size=batch_size
        )

        if result.get('success', False):
            app.logger.info(f'DeepSeek字幕校正成功: 处理时间={result.get("processing_time", 0):.2f}秒')

            # 如果有书名，尝试保存校正后的字幕到内存
            if book_name:
                try:
                    corrected_content = result.get('corrected_subtitle', '')
                    if corrected_content:
                        # 生成校正后的字幕文件名
                        corrected_filename = f"corrected_{int(time.time())}.srt"
                        file_key = f"{book_name}_{corrected_filename}"

                        # 保存到内存文件系统
                        if not hasattr(upload_file, 'memory_files'):
                            upload_file.memory_files = {}

                        upload_file.memory_files[file_key] = {
                            'content': corrected_content.encode('utf-8'),
                            'filename': corrected_filename,
                            'size': len(corrected_content.encode('utf-8')),
                            'type': 'corrected_subtitle',
                            'original_subtitle': subtitle_text,
                            'reference_text': original_text,
                            'correction_time': datetime.now().isoformat(),
                            'processing_time': result.get('processing_time', 0)
                        }

                        result['saved_filename'] = corrected_filename
                        result['file_key'] = file_key
                        app.logger.info(f'校正后的字幕已保存到内存: {corrected_filename}')

                except Exception as save_e:
                    app.logger.warning(f'保存校正后的字幕失败: {save_e}')
                    # 保存失败不影响主功能

            return jsonify(result)
        else:
            app.logger.error(f'DeepSeek字幕校正失败: {result.get("error", "未知错误")}')
            return jsonify(result), 500

    except Exception as e:
        app.logger.error(f'DeepSeek字幕校正异常: {e}')
        return jsonify({
            'success': False,
            'error': f'字幕校正失败: {str(e)}',
            'original_subtitle': data.get('subtitle_text', '') if 'data' in locals() else '',
            'reference_text': data.get('original_text', '') if 'data' in locals() else ''
        }), 500


@app.route('/api/deepseek-correct-subtitle-web', methods=['POST'])
def correct_subtitle_via_web():
    """通过DeepSeek API进行字幕校正（修复版本）"""
    try:
        # 获取请求数据
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400

        # 获取参数 - 支持多种参数名以兼容前端
        subtitle_text = data.get('subtitle_text', '').strip()
        original_text = data.get('original_text', '').strip()
        # 尝试从多个可能的键获取API密钥
        api_key = (data.get('api_key', '').strip() or
                   data.get('api', '').strip() or
                   data.get('apiKey', '').strip() or
                   data.get('key', '').strip())
        
        # 如果请求中没有API密钥，尝试从环境变量获取
        if not api_key:
            api_key = os.getenv('DEEPSEEK_API_KEY')

        enable_deepthink = data.get('enable_deepthink', True)
        book_name = data.get('book_name', '').strip()

        # 添加参数调试日志
        app.logger.info(f'解析后的参数: subtitle_text长度={len(subtitle_text)}, original_text长度={len(original_text)}, api_key存在={bool(api_key)}, api_key长度={len(api_key) if api_key else 0}')

        # 验证必填参数
        if not subtitle_text:
            return jsonify({
                'success': False,
                'error': '字幕文本不能为空'
            }), 400

        if not original_text:
            return jsonify({
                'success': False,
                'error': '原文文本不能为空'
            }), 400

        if not api_key:
            app.logger.error('API密钥验证失败: api_key为空')
            return jsonify({
                'success': False,
                'error': 'DeepSeek API密钥不能为空'
            }), 400

        app.logger.info(f'开始通过DeepSeek API进行字幕校正: 书名={book_name}')

        # 先验证API密钥是否有效
        try:
            from deepseek_api import DeepSeekAPI
            test_client = DeepSeekAPI(api_key=api_key)

            # 发送一个简单的测试请求来验证API密钥
            test_response = test_client._make_request("v1/chat/completions", {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 10
            }, max_retries=1, timeout=10)

            if test_response.get('error'):
                app.logger.error(f'API密钥验证失败: {test_response.get("error")}')
                return jsonify({
                    'success': False,
                    'error': f'API密钥验证失败: {test_response.get("error")}'
                }), 400

            app.logger.info('API密钥验证成功，开始字幕校正')

        except Exception as api_e:
            app.logger.error(f'API密钥验证异常: {str(api_e)}')
            return jsonify({
                'success': False,
                'error': f'API密钥验证失败: {str(api_e)}'
            }), 400

        # API验证成功，让用户选择使用模式
        # 检查是否用户指定了模式偏好
        use_web_mode = data.get('use_web_mode', False)  # 默认使用API模式
        headless = data.get('headless', True)  # 默认使用无头模式

        # 统计字幕条目数量
        import re
        subtitle_entries = re.findall(r'^\d+$', subtitle_text, re.MULTILINE)
        entry_count = len(subtitle_entries)
        
        # 构建统一的提示词（用于网页交互模式）
        prompt = f"""你是一个专业的字幕校正专家。请根据提供的原文，校正以下字幕内容。

【核心要求 - 必须严格遵守】
输入字幕共有 {entry_count} 条，输出也必须是 {entry_count} 条！
绝对不允许合并、删除或增加任何字幕条目！
绝对不允许调整字幕内容的分布！

请根据第二段原文文本，对第一段字幕文本进行精确校对。具体要求如下：

1. **错别字校正**：
   - 只校正每条字幕中的错别字
   - 原文仅用于识别正确的字，不用于调整内容分布
   - 不要根据原文的句子完整性来调整字幕内容
   - 即使原文是完整的一句话，字幕分成多条也要保持分开
   - 例如：原文"第一回　甄士隱夢幻識通靈　賈雨村風塵懷閨秀"，如果字幕分成2条，就保持2条，不要合并

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
直接输出字幕，不要添加任何解释或说明。"""

        if use_web_mode:
            # 用户选择使用网页交互模式
            app.logger.info('用户选择使用网页交互模式')
            app.logger.warning('⚠️ 网页交互模式需要登录，建议使用API模式。自动切换到API模式...')
            use_web_mode = False  # 暂时禁用网页交互模式，自动使用API模式
            
            # 以下代码暂时注释，等登录问题解决后再启用
            # try:
            #     # 导入最终优化版网页接口
            #     from final_web_interface import StableDeepSeekWebInterface
            #
            #     with StableDeepSeekWebInterface(headless=headless) as web_client:
            #         result = web_client.correct_subtitle_via_web(
            #             subtitle_text=subtitle_text,
            #             original_text=original_text,
            #             prompt=prompt,
            #             api_key=api_key
            #         )
            #
            #         app.logger.info(f'优化网页交互字幕校正结果: {result}')
            #         return jsonify(result)
            #
            # except Exception as e:
            #     app.logger.error(f'优化网页交互字幕校正异常: {e}')
            #     import traceback
            #     app.logger.error(f'错误堆栈: {traceback.format_exc()}')
            #
            #     # 检测是否是WebDriver相关错误，如果是，切换回API模式
            #     if any(keyword in str(e).lower() for keyword in ['disconnected', 'invalid session', 'chrome not reachable']):
            #         app.logger.warning('检测到WebDriver错误，自动切换到API模式')
            #         use_web_mode = False  # 强制使用API模式
            #     else:
            #         return jsonify({
            #             'success': False,
            #             'error': f'网页交互字幕校正失败: {str(e)}',
            #             'original_subtitle': subtitle_text,
            #             'reference_text': original_text
            #         }), 500

        # 使用API模式（默认或网页模式失败后回退）
        app.logger.info(f'使用API模式进行字幕校正')
        try:
            client = DeepSeekAPI(api_key=api_key)
            result = client.correct_subtitle(
                subtitle_text=subtitle_text,
                original_text=original_text,
                enable_deepthink=enable_deepthink
            )
            app.logger.info(f'DeepSeek API字幕校正结果: {result}')

            if result.get('success', False):
                # 添加书名到结果
                result['book_name'] = book_name

                # 如果有书名，保存校正后的字幕
                if book_name:
                    try:
                        corrected_content = result.get('corrected_subtitle', '')
                        if corrected_content:
                            # 生成校正后的文件名
                            corrected_filename = f"subtitle_corrected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt"
                            file_key = f"{book_name}_{corrected_filename}"

                            # 保存到内存
                            if not hasattr(upload_file, 'memory_files'):
                                upload_file.memory_files = {}

                            upload_file.memory_files[file_key] = {
                                'content': corrected_content.encode('utf-8'),
                                'filename': corrected_filename,
                                'size': len(corrected_content.encode('utf-8')),
                                'type': 'corrected_subtitle',
                                'original_filename': 'web_input',
                                'reference_filename': 'web_input',
                                'original_subtitle': subtitle_text,
                                'reference_text': original_text,
                                'correction_time': datetime.now().isoformat(),
                                'processing_time': result.get('processing_time', 0),
                                'correction_method': 'api_direct'
                            }

                            result['saved_filename'] = corrected_filename
                            result['file_key'] = file_key
                            app.logger.info(f'API字幕校正完成，已保存: {corrected_filename}')

                    except Exception as save_e:
                        app.logger.warning(f'保存校正结果失败: {save_e}')

                app.logger.info(f'DeepSeek API字幕校正成功: 处理时间={result.get("processing_time", 0):.2f}秒')
                return jsonify(result)
            else:
                app.logger.error(f'DeepSeek API字幕校正失败: {result.get("error", "未知错误")}')
                return jsonify(result)

        except Exception as e:
            import traceback
            app.logger.error(f'API字幕校正过程中发生错误: {e}')
            app.logger.error(f'错误堆栈: {traceback.format_exc()}')

            # 确保错误信息是字符串格式
            if isinstance(e, dict):
                error_message = json.dumps(e, ensure_ascii=False)
            else:
                error_message = str(e)

            return jsonify({
                'success': False,
                'error': f'DeepSeek API字幕校正失败: {error_message}',
                'original_subtitle': data.get('subtitle_text', '') if 'data' in locals() else '',
                'reference_text': data.get('original_text', '') if 'data' in locals() else ''
            }), 500

    except Exception as e:
        app.logger.error(f'DeepSeek API字幕校正异常: {e}')
        # 确保错误信息是字符串格式
        if isinstance(e, dict):
            error_message = json.dumps(e, ensure_ascii=False)
        else:
            error_message = str(e)

        return jsonify({
            'success': False,
            'error': f'DeepSeek API字幕校正失败: {error_message}',
            'original_subtitle': data.get('subtitle_text', '') if 'data' in locals() else '',
            'reference_text': data.get('original_text', '') if 'data' in locals() else ''
        }), 500
        app.logger.error(f'DeepSeek网页交互字幕校正异常: {e}')
        # 确保错误信息是字符串格式
        if isinstance(e, dict):
            error_message = json.dumps(e, ensure_ascii=False)
        else:
            error_message = str(e)
        
        return jsonify({
            'success': False,
            'error': f'网页交互字幕校正失败: {error_message}'
        }), 500@app.route('/api/deepseek-upload-and-correct', methods=['POST'])
def upload_and_correct_subtitle():
    """上传文件并进行DeepSeek字幕校正"""
    try:
        # 检查文件上传
        if 'subtitle_file' not in request.files or 'original_file' not in request.files:
            return jsonify({
                'success': False,
                'error': '请同时上传字幕文件和原文文件'
            }), 400

        subtitle_file = request.files['subtitle_file']
        original_file = request.files['original_file']

        if subtitle_file.filename == '' or original_file.filename == '':
            return jsonify({
                'success': False,
                'error': '请选择有效的文件'
            }), 400

        # 获取其他参数
        api_key = request.form.get('api_key', '').strip()
        
        # 如果请求中没有API密钥，尝试从环境变量获取
        if not api_key:
            api_key = os.getenv('DEEPSEEK_API_KEY')
            
        enable_deepthink = request.form.get('enable_deepthink', 'true').lower() == 'true'
        book_name = request.form.get('book_name', '').strip()

        # 验证文件类型
        allowed_extensions = {'.srt', '.txt', '.vtt'}
        subtitle_ext = os.path.splitext(subtitle_file.filename)[1].lower()
        original_ext = os.path.splitext(original_file.filename)[1].lower()

        if subtitle_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': f'字幕文件不支持 {subtitle_ext} 格式，支持的格式: {", ".join(allowed_extensions)}'
            }), 400

        if original_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': f'原文文件不支持 {original_ext} 格式，支持的格式: {", ".join(allowed_extensions)}'
            }), 400

        # 读取文件内容
        subtitle_text = subtitle_file.read().decode('utf-8')
        original_text = original_file.read().decode('utf-8')

        if not subtitle_text.strip():
            return jsonify({
                'success': False,
                'error': '字幕文件内容为空'
            }), 400

        if not original_text.strip():
            return jsonify({
                'success': False,
                'error': '原文文件内容为空'
            }), 400

        app.logger.info(f'上传文件进行DeepSeek字幕校正: 字幕={subtitle_file.filename}, 原文={original_file.filename}, 书名={book_name}')

        # 获取DeepSeek客户端并执行校正
        if api_key:
            client = get_deepseek_client(api_key)
        else:
            client = get_deepseek_client()

        # 执行字幕校正
        result = client.correct_subtitle(
            subtitle_text=subtitle_text,
            original_text=original_text,
            enable_deepthink=enable_deepthink
        )

        if result.get('success', False):
            # 添加文件信息到结果
            result['subtitle_filename'] = subtitle_file.filename
            result['original_filename'] = original_file.filename
            result['book_name'] = book_name

            # 如果有书名，保存校正后的字幕
            if book_name:
                try:
                    corrected_content = result.get('corrected_subtitle', '')
                    if corrected_content:
                        # 生成校正后的文件名
                        base_name = os.path.splitext(subtitle_file.filename)[0]
                        corrected_filename = f"{base_name}_corrected.srt"
                        file_key = f"{book_name}_{corrected_filename}"

                        # 保存到内存
                        if not hasattr(upload_file, 'memory_files'):
                            upload_file.memory_files = {}

                        upload_file.memory_files[file_key] = {
                            'content': corrected_content.encode('utf-8'),
                            'filename': corrected_filename,
                            'size': len(corrected_content.encode('utf-8')),
                            'type': 'corrected_subtitle',
                            'original_filename': subtitle_file.filename,
                            'reference_filename': original_file.filename,
                            'original_subtitle': subtitle_text,
                            'reference_text': original_text,
                            'correction_time': datetime.now().isoformat(),
                            'processing_time': result.get('processing_time', 0)
                        }

                        result['saved_filename'] = corrected_filename
                        result['file_key'] = file_key
                        app.logger.info(f'文件上传校正完成，已保存: {corrected_filename}')

                except Exception as save_e:
                    app.logger.warning(f'保存校正结果失败: {save_e}')

            app.logger.info(f'DeepSeek文件上传字幕校正成功: 处理时间={result.get("processing_time", 0):.2f}秒')
            return jsonify(result)
        else:
            app.logger.error(f'DeepSeek文件上传字幕校正失败: {result.get("error", "未知错误")}')
            return jsonify(result), 500

    except Exception as e:
        app.logger.error(f'DeepSeek文件上传字幕校正异常: {e}')
        return jsonify({
            'success': False,
            'error': f'文件上传校正失败: {str(e)}'
        }), 500


@app.route('/api/deepseek-get-corrected-subtitles', methods=['GET'])
def get_corrected_subtitles():
    """获取校正后的字幕文件列表"""
    try:
        book_name = request.args.get('book_name', '').strip()

        if not book_name:
            return jsonify({
                'success': False,
                'error': '书名不能为空'
            }), 400

        if not hasattr(upload_file, 'memory_files'):
            return jsonify({
                'success': True,
                'corrected_subtitles': []
            })

        # 筛选该校正后的字幕文件
        corrected_subtitles = []
        for key, file_info in upload_file.memory_files.items():
            if key.startswith(f"{book_name}_") and file_info.get('type') == 'corrected_subtitle':
                corrected_subtitles.append({
                    'file_key': key,
                    'filename': file_info.get('filename', ''),
                    'size': file_info.get('size', 0),
                    'original_filename': file_info.get('original_filename', ''),
                    'reference_filename': file_info.get('reference_filename', ''),
                    'correction_time': file_info.get('correction_time', ''),
                    'processing_time': file_info.get('processing_time', 0)
                })

        # 按校正时间排序
        corrected_subtitles.sort(key=lambda x: x['correction_time'], reverse=True)

        return jsonify({
            'success': True,
            'corrected_subtitles': corrected_subtitles,
            'count': len(corrected_subtitles)
        })

    except Exception as e:
        app.logger.error(f'获取校正后字幕列表失败: {e}')
        return jsonify({
            'success': False,
            'error': f'获取失败: {str(e)}'
        }), 500


@app.route('/api/extract-timings-from-subtitles', methods=['POST'])
def extract_timings_from_subtitles():
    """
    从字幕文件中提取翻页时间点
    """
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400
        
        # 获取参数
        book_name = data.get('book_name', '').strip()
        subtitle_filename = data.get('subtitle_filename', '').strip()
        start_page = int(data.get('start_page', 1))
        end_page = int(data.get('end_page', 10))
        is_vertical_layout = data.get('is_vertical_layout', False)
        page_content = data.get('page_content', [])
        
        # 验证必填参数
        if not book_name:
            return jsonify({
                'success': False,
                'error': '书名不能为空'
            }), 400
            
        if not subtitle_filename:
            return jsonify({
                'success': False,
                'error': '字幕文件名不能为空'
            }), 400
        
        if start_page < 1:
            return jsonify({
                'success': False,
                'error': '起始页码必须大于0'
            }), 400
            
        if end_page < start_page:
            return jsonify({
                'success': False,
                'error': '结束页码不能小于起始页码'
            }), 400
        
        app.logger.info(f'开始从字幕提取翻页时间点: 书名={book_name}, 字幕文件={subtitle_filename}, 页面范围={start_page}-{end_page}, 竖排={is_vertical_layout}')
        
        # 获取字幕文件内容
        subtitle_content = None
        subtitle_path = None
        
        # 首先尝试从内存中获取
        subtitle_key = f"{book_name}_{subtitle_filename}"
        if hasattr(upload_file, 'memory_files') and subtitle_key in upload_file.memory_files:
            subtitle_data = upload_file.memory_files[subtitle_key]
            subtitle_content = subtitle_data['content'].decode('utf-8')
            app.logger.info(f'从内存中获取字幕文件: {subtitle_filename}')
        else:
            # 尝试从文件系统读取
            subtitle_path = os.path.join("电子书", book_name, "字幕文件", subtitle_filename)
            
            if not os.path.exists(subtitle_path):
                return jsonify({
                    'success': False,
                    'error': f'找不到字幕文件: {subtitle_filename}'
                }), 404
            
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            
            app.logger.info(f'从文件系统读取字幕文件: {subtitle_path}')
        
        # 解析字幕文件
        import re
        subtitle_blocks = re.split(r'\r?\n\r?\n', subtitle_content.strip())
        
        # 提取时间轴信息
        timings = []
        time_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})')
        
        for block in subtitle_blocks:
            lines = block.split('\n')
            if len(lines) >= 2:
                time_line = lines[1]
                match = time_pattern.match(time_line)
                if match:
                    start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = match.groups()
                    start_time = int(start_h) * 3600 + int(start_m) * 60 + int(start_s) + int(start_ms) / 1000
                    end_time = int(end_h) * 3600 + int(end_m) * 60 + int(end_s) + int(end_ms) / 1000
                    timings.append({
                        'start': start_time,
                        'end': end_time,
                        'text': '\n'.join(lines[2:]) if len(lines) > 2 else ''
                    })
        
        if not timings:
            return jsonify({
                'success': False,
                'error': '字幕文件中没有找到有效的时间轴信息'
            }), 400
        
        app.logger.info(f'解析字幕文件完成，共找到 {len(timings)} 个字幕条目')
        
        # 计算翻页时间点
        page_timings = []
        total_pages = end_page - start_page + 1
        
        # 如果是竖排模式，需要两页合并为一个背景
        if is_vertical_layout:
            # 调整总页数为偶数
            adjusted_total_pages = total_pages if total_pages % 2 == 0 else total_pages - 1
            num_transitions = adjusted_total_pages // 2
            
            # 计算每个翻页点的时间
            if len(timings) >= num_transitions:
                # 直接使用字幕时间点作为翻页点
                for i in range(num_transitions):
                    page_timings.append(timings[i]['start'])
            else:
                # 字幕条目不足，均匀分布时间点
                total_duration = timings[-1]['end'] if timings else 0
                interval = total_duration / (num_transitions + 1)
                for i in range(1, num_transitions + 1):
                    page_timings.append(i * interval)
        else:
            # 普通模式，每页一个翻页点
            num_transitions = total_pages
            
            # 计算每个翻页点的时间
            if len(timings) >= num_transitions:
                # 直接使用字幕时间点作为翻页点
                for i in range(num_transitions):
                    page_timings.append(timings[i]['start'])
            else:
                # 字幕条目不足，均匀分布时间点
                total_duration = timings[-1]['end'] if timings else 0
                interval = total_duration / (num_transitions + 1)
                for i in range(1, num_transitions + 1):
                    page_timings.append(i * interval)
        
        app.logger.info(f'计算翻页时间点完成，共 {len(page_timings)} 个时间点')
        
        # 返回结果
        return jsonify({
            'success': True,
            'page_timings': page_timings,
            'total_pages': total_pages,
            'num_transitions': num_transitions if is_vertical_layout else total_pages,
            'subtitle_entries': len(timings),
            'is_vertical_layout': is_vertical_layout,
            'start_page': start_page,
            'end_page': end_page
        })
        
    except Exception as e:
        app.logger.error(f'从字幕提取翻页时间点失败: {e}')
        import traceback
        app.logger.error(f'错误堆栈: {traceback.format_exc()}')
        return jsonify({
            'success': False,
            'error': f'提取翻页时间点失败: {str(e)}'
        }), 500









if __name__ == '__main__':
    import argparse
    import logging
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Web Video Creator')
    parser.add_argument('--port', type=int, default=5008, help='Port to run the server on')
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log')
        ]
    )
    
    # Add WebSocket log handler to root logger to capture all logs
    root_logger = logging.getLogger()
    ws_handler = WebSocketLogHandler(socketio)
    ws_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ws_handler.setFormatter(formatter)
    root_logger.addHandler(ws_handler)
    
    # Check FFmpeg availability
    if not check_ffmpeg():
        print("ERROR: FFmpeg not found. Please install FFmpeg:")
        print("  brew install ffmpeg")
        exit(1)

    # Initialize DeepSeek API from config
    try:
        init_deepseek_from_config()
        print("DeepSeek API initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize DeepSeek API: {e}")
        print("DeepSeek subtitle correction feature will not be available")

    print("Starting Web Video Creator...")
    print(f"Open http://localhost:{args.port} in your browser")
    socketio.run(app, host='0.0.0.0', port=args.port, debug=True, allow_unsafe_werkzeug=True)