import threading
import os
import time
from datetime import datetime
import numpy as np
import soundcard as sc
import soundfile as sf
import asyncio
import requests
import json

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

    async def _upload_file_for_asr(self, file_path, api_key, model="qwen3-asr-flash-filetrans"):
        """Upload local audio file to DashScope temporary storage and return oss:// URL

        Args:
            file_path: Path to local audio file
            api_key: DashScope API key
            model: Model name for getting upload policy

        Returns:
            oss:// URL string or None on failure
        """
        # Get upload policy
        policy_url = f"https://dashscope.aliyuncs.com/api/v1/uploads?action=getPolicy&model={model}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            self.log("获取文件上传凭证...")
            resp = requests.get(policy_url, headers=headers)
            if resp.status_code != 200:
                self.log(f"获取上传凭证失败: {resp.status_code} - {resp.text}")
                return None

            policy_data = resp.json()
            data = policy_data.get("data", {})

            # Extract OSS multipart upload credentials
            upload_host = data.get("upload_host")
            policy = data.get("policy")
            signature = data.get("signature")
            upload_dir = data.get("upload_dir")
            oss_access_key_id = data.get("oss_access_key_id")
            x_oss_object_acl = data.get("x_oss_object_acl", "private")
            x_oss_forbid_overwrite = data.get("x_oss_forbid_overwrite", "true")

            if not all([upload_host, policy, signature, upload_dir, oss_access_key_id]):
                self.log(f"上传凭证无效: 缺少必要字段")
                self.log(f"Policy data: {list(data.keys())}")
                return None

            # Construct OSS object key: upload_dir + "/" + filename
            filename = os.path.basename(file_path)
            oss_key = f"{upload_dir}/{filename}"
            upload_url = f"{upload_host}/"
            oss_url = f"oss://{oss_key}"

            # Read file content
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Build multipart/form-data for OSS upload
            files = {
                "file": (filename, file_data)
            }
            data_dict = {
                "OSSAccessKeyId": oss_access_key_id,
                "policy": policy,
                "Signature": signature,
                "key": oss_key,
                "x-oss-object-acl": x_oss_object_acl,
                "x-oss-forbid-overwrite": x_oss_forbid_overwrite,
                "success_action_status": "200"
            }

            # Upload file via multipart/form-data POST
            self.log(f"上传音频文件: {filename}")
            upload_resp = requests.post(upload_url, files=files, data=data_dict)

            if upload_resp.status_code != 200:
                self.log(f"文件上传失败: {upload_resp.status_code} - {upload_resp.text[:200]}")
                return None

            self.log(f"文件上传成功: {oss_url}")
            return oss_url

        except Exception as e:
            self.log(f"文件上传异常: {e}")
            return None

    async def _poll_transcription_result(self, task_id, api_key, poll_interval=2, max_poll_time=300):
        """Poll transcription task status until completion

        Args:
            task_id: Transcription task ID
            api_key: DashScope API key
            poll_interval: Seconds between polls
            max_poll_time: Maximum seconds to wait

        Returns:
            Transcription text or None on failure
        """
        query_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < max_poll_time:
            poll_count += 1
            await asyncio.sleep(poll_interval)

            try:
                resp = requests.get(query_url, headers=headers)
                if resp.status_code != 200:
                    self.log(f"查询任务状态失败: {resp.status_code}")
                    continue

                data = resp.json()
                output = data.get("output", {})
                status = output.get("task_status", "").upper()

                if poll_count % 5 == 0:  # Log every 10 seconds
                    self.log(f"转录任务状态: {status}")

                if status == "SUCCEEDED":
                    # API response structure: {task_id, task_status, result: {transcription_url}}
                    result = output.get("result", {})
                    transcription_url = result.get("transcription_url")

                    if not transcription_url:
                        self.log("转录成功但未找到 transcription_url")
                        return None

                    self.log(f"尝试从 URL 获取结果...")
                    try:
                        trans_resp = requests.get(transcription_url)
                        if trans_resp.status_code == 200:
                            trans_data = trans_resp.json()
                            # Log structure for debugging
                            self.log(f"URL 响应结构: {list(trans_data.keys())}")

                            # Try different possible structures
                            # Structure 1: {results: [{text: "...", ...}, ...]}
                            if "results" in trans_data:
                                transcripts = trans_data["results"]
                                if transcripts:
                                    text_parts = []
                                    for item in transcripts:
                                        text_parts.append(item.get("text", ""))
                                    text = "".join(text_parts)
                                    if text:
                                        self.log(f"从 results 获取到文本: {len(text)} 字符")
                                        return text

                            # Structure 2: {transcripts: [{text: "...", ...}, ...]}
                            if "transcripts" in trans_data:
                                transcripts = trans_data["transcripts"]
                                if transcripts:
                                    text_parts = []
                                    for item in transcripts:
                                        text_parts.append(item.get("text", ""))
                                    text = "".join(text_parts)
                                    if text:
                                        self.log(f"从 transcripts 获取到文本: {len(text)} 字符")
                                        return text

                            # Structure 3: {text: "..."}
                            if "text" in trans_data:
                                text = trans_data["text"]
                                if text:
                                    self.log(f"从 text 获取到文本: {len(text)} 字符")
                                    return text

                            # Structure 4: {transcription_text: "..."}
                            if "transcription_text" in trans_data:
                                text = trans_data["transcription_text"]
                                if text:
                                    self.log(f"从 transcription_text 获取到文本: {len(text)} 字符")
                                    return text

                            self.log(f"URL 响应中未找到文本内容。响应结构: {str(trans_data)[:300]}...")
                            return None
                        else:
                            self.log(f"获取 URL 失败: {trans_resp.status_code}")
                            return None
                    except Exception as e:
                        self.log(f"从 URL 获取结果异常: {e}")
                        return None

                elif status in ("FAILED", "UNKNOWN"):
                    error_msg = output.get("message", "Unknown error")
                    self.log(f"转录任务失败: {status} - {error_msg}")
                    return None

            except Exception as e:
                self.log(f"轮询任务状态异常: {e}")

        self.log(f"转录任务超时 ({max_poll_time}秒)")
        return None

    async def transcribe(self, file_path, api_key):
        """Transcribe audio file using DashScope qwen3-asr-flash-filetrans API

        This method uploads the file to temporary storage and polls for the result.
        """
        if not file_path or not os.path.exists(file_path):
            return ""

        self.log("正在转录音频 (Qwen3-ASR-FileTrans)...")

        try:
            # Load configuration
            try:
                from config import Config
                model = Config.ASR_MODEL
                poll_interval = Config.ASR_POLL_INTERVAL
                max_poll_time = Config.ASR_MAX_POLL_TIME
            except ImportError:
                model = "qwen3-asr-flash-filetrans"
                poll_interval = 2
                max_poll_time = 300

            # Step 1: Upload file to temporary storage
            oss_url = await self._upload_file_for_asr(file_path, api_key, model)
            if not oss_url:
                return ""

            # Step 2: Submit transcription task
            submit_url = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
                "X-DashScope-OssResourceResolve": "enable"  # Required for oss:// URLs
            }

            payload = {
                "model": model,
                "input": {
                    "file_url": oss_url
                },
                "parameters": {
                    "channel_id": [0],
                    "enable_itn": False
                }
            }

            self.log("提交转录任务...")
            submit_resp = requests.post(
                submit_url,
                headers=headers,
                data=json.dumps(payload)
            )

            if submit_resp.status_code != 200:
                self.log(f"提交任务失败: {submit_resp.status_code} - {submit_resp.text}")
                return ""

            submit_data = submit_resp.json()
            output = submit_data.get("output", {})

            if "task_id" not in output:
                self.log(f"响应中缺少 task_id: {submit_data}")
                return ""

            task_id = output["task_id"]
            self.log(f"任务已提交 (ID: {task_id[:12]}...)")

            # Step 3: Poll for result
            text = await self._poll_transcription_result(
                task_id, api_key, poll_interval, max_poll_time
            )

            if text:
                self.log(f"转录成功: {text[:20]}...")
                return text
            else:
                self.log("转录失败或结果为空")
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
