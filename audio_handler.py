import threading
import os
import time
import glob
import shutil
from datetime import datetime
import numpy as np
import soundcard as sc
import soundfile as sf
import asyncio

class AudioHandler:
    def __init__(self, output_dir=None, transcript_dir=None, log_callback=None):
        self.log_callback = log_callback

        # Use build config paths if available
        try:
            from build_config import get_logs_path
            logs_path = get_logs_path()
            self.output_dir = output_dir or os.path.join(logs_path, "audio")
            self.transcript_dir = transcript_dir or os.path.join(logs_path, "transcripts")
        except ImportError:
            self.output_dir = output_dir or "logs/audio"
            self.transcript_dir = transcript_dir or "logs/transcripts"

        # Create directories if they don't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if not os.path.exists(self.transcript_dir):
            os.makedirs(self.transcript_dir)
        
        self.is_recording = False
        self.frames = []
        self.thread = None
        self.sample_rate = 16000
        self._stop_event = threading.Event()
        
        # Track current session files for potential cleanup
        self.session_audio_files = []
        self.session_transcript_files = []

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(f"[Audio] {msg}")

    def start_recording(self):
        """Start recording in a background thread"""
        if self.is_recording:
            return
        
        try:
            # Test if we can access microphone/loopback
            sc.default_speaker()
        except Exception as e:
            self.log(f"无法访问音频设备: {e}")
            return

        self.is_recording = True
        self._stop_event.clear()
        self.frames = []
        self.thread = threading.Thread(target=self._record_loop)
        self.thread.daemon = True
        self.thread.start()
        self.log("开始录制音频...")

    def _record_loop(self):
        try:
            # Use default speaker loopback
            speaker = sc.default_speaker()
            mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            
            with mic.recorder(samplerate=self.sample_rate) as recorder:
                while not self._stop_event.is_set():
                    # Record 1 second chunks
                    chunk = recorder.record(numframes=self.sample_rate)
                    self.frames.append(chunk)
        except Exception as e:
            self.log(f"录音循环出错: {e}")
            self.is_recording = False

    def stop_and_save(self):
        """Stop recording and save to WAV. Returns filename or None."""
        if not self.is_recording:
            return None

        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        
        self.is_recording = False
        
        if not self.frames:
            self.log("没有录制到数据")
            return None

        try:
            data = np.concatenate(self.frames)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.output_dir, f"audio_{timestamp}.wav")
            sf.write(filename, data, self.sample_rate)
            self.session_audio_files.append(filename)
            return filename
        except Exception as e:
            self.log(f"保存音频失败: {e}")
            return None

    def save_transcript(self, text):
        """Save transcript to text file"""
        if not text:
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.transcript_dir, f"transcript_{timestamp}.txt")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            self.session_transcript_files.append(filename)
            self.log(f"转录文本已保存: {filename}")
            return filename
        except Exception as e:
            self.log(f"保存转录文本失败: {e}")
            return None

    async def transcribe(self, file_path, api_key):
        """Transcribe using DashScope Qwen3-ASR"""
        if not file_path or not os.path.exists(file_path):
            return ""

        self.log("正在转录音频 (Qwen3-ASR)...")
        try:
            import dashscope
            dashscope.api_key = api_key
            
            # Use run_in_executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            
            def _call_dashscope():
                messages = [
                    {
                        "role": "system",
                        "content": [{"text": ""}]
                    },
                    {
                        "role": "user",
                        "content": [
                            {"audio": f"file://{os.path.abspath(file_path)}"}
                        ]
                    }
                ]
                
                response = dashscope.MultiModalConversation.call(
                    api_key=api_key,
                    model="qwen3-asr-flash",
                    messages=messages,
                    result_format="message",
                    asr_options={
                        "enable_lid": True,
                        "enable_itn": False
                    }
                )
                return response

            response = await loop.run_in_executor(None, _call_dashscope)
            
            if response.status_code == 200:
                # Parse result from MultiModalConversation structure
                # Typically: response.output.choices[0].message.content[0]['text']
                text_content = ""
                try:
                    if hasattr(response, 'output') and response.output.choices:
                        message = response.output.choices[0].message
                        if isinstance(message.content, list):
                            for item in message.content:
                                if 'text' in item:
                                    text_content += item['text']
                        elif isinstance(message.content, str):
                            text_content = message.content
                except Exception as parse_err:
                    self.log(f"解析响应失败: {parse_err}")
                    return ""

                if text_content:
                    self.log(f"转录成功: {text_content[:20]}...")
                    return text_content
                else:
                    self.log("转录结果为空")
                    return ""
            else:
                self.log(f"转录失败: {response.message}")
                return ""
                
        except ImportError:
            self.log("请安装 dashscope 库: pip install dashscope")
            return ""
        except Exception as e:
            self.log(f"转录异常: {e}")
            return ""

    def clear_audio_files(self):
        """Delete all audio files from current session"""
        count = 0
        for f in self.session_audio_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    count += 1
            except Exception as e:
                self.log(f"删除音频文件失败 {f}: {e}")
        self.session_audio_files = []
        self.log(f"已清理 {count} 个音频文件")

    def clear_transcript_files(self):
        """Delete all transcript files from current session"""
        count = 0
        for f in self.session_transcript_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    count += 1
            except Exception as e:
                self.log(f"删除转录文件失败 {f}: {e}")
        self.session_transcript_files = []
        self.log(f"已清理 {count} 个转录文件")
