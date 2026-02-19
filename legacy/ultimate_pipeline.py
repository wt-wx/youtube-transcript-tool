import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from faster_whisper import WhisperModel

# ================= 配置区 =================
CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_NAME = "YouTube_Blogger_Automation"
SHEET_NAME = "Production"
AUDIO_OUTPUT_DIR = "downloads/audio"
# Whisper 模型大小支持: tiny, base, small, medium, large-v3
# tiny/base 速度最快，适合 VPS CPU 运行；small/medium 准确率更高
WHISPER_MODEL_SIZE = "base" 
DEVICE = "cpu" # 如果 VPS 有 GPU 改为 "cuda"
ComputeType = "int8" # CPU 上推荐使用 int8 提高速度

# 确保音频保存目录存在
if not os.path.exists(AUDIO_OUTPUT_DIR):
    os.makedirs(AUDIO_OUTPUT_DIR)

# ================= 授权 & 初始化 =================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)
production_sheet = spreadsheet.worksheet(SHEET_NAME)

# 加载 Faster-Whisper 模型
print(f"正在加载 Whisper 模型 ({WHISPER_MODEL_SIZE})...")
model = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=ComputeType)

# ================= 核心流水线 =================

def download_audio(video_url, video_id):
    """使用 yt-dlp 下载音频流并保持"""
    output_path = os.path.join(AUDIO_OUTPUT_DIR, f"{video_id}.mp3")
    
    # 如果文件已存在，跳过下载
    if os.path.exists(output_path):
        print(f"音频文件已存在: {output_path}")
        return output_path

    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'outtmpl': os.path.join(AUDIO_OUTPUT_DIR, f"{video_id}.%(ext)s"),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    print(f"正在从 YouTube 下载音频: {video_id}...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return output_path

def transcribe_audio(audio_path):
    """使用 Faster-Whisper 将语音转为文字"""
    print(f"正在进行 AI 转录: {os.path.basename(audio_path)}...")
    # beam_size=5 是默认值，增大可以提高一点准确率但变慢
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    print(f"检测到语言: {info.language} (置信度: {info.language_probability:.2f})")
    
    full_text = []
    for segment in segments:
        full_text.append(segment.text)
        # 如果是实时输出可以打开下面这行
        # print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
        
    return " ".join(full_text)

def ultimate_pipeline(limit=5):
    """自动化流水线主入口"""
    records = production_sheet.get_all_values()
    api = YouTubeTranscriptApi()
    
    processed_count = 0
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= limit:
            print(f"\n已完成本次设定的 {limit} 条目标，流水线停止。")
            break
            
        video_url = row[0]
        video_id = row[1]
        status = row[2] if len(row) > 2 else ""
        transcript_cell = row[4] if len(row) > 4 else ""
        
        # 仅处理【等待处理】或【字幕不可用】且【E列为空】的行
        if video_id and not transcript_cell:
            print(f"\n--- 处理进度: [{processed_count + 1}/{limit}] ---")
            print(f"视频 ID: {video_id}")
            
            # 步骤 1: 尝试获取原放字幕（省时省力）
            try:
                print("尝试获取官方字幕...")
                transcript_obj = api.fetch(video_id, languages=['zh-Hans', 'zh-Hant', 'en'])
                srt = transcript_obj.to_raw_data()
                final_text = " ".join([t['text'] for t in srt])
                source_mark = "官方字幕"
            except Exception:
                # 步骤 2: 官方字幕不可用，启动 AI 转录
                print("官方磁条不可用，启动 AI 转录流程...")
                try:
                    # 下载音频 (保留文件)
                    audio_path = download_audio(video_url, video_id)
                    # Whisper 转录
                    final_text = transcribe_audio(audio_path)
                    source_mark = f"AI转录({WHISPER_MODEL_SIZE})"
                except Exception as e:
                    print(f"❌ AI 转录失败: {str(e)}")
                    production_sheet.update_cell(i, 3, "AI转录失败")
                    continue

            # 步骤 3: 写回 Google Sheets
            production_sheet.update_cell(i, 5, final_text)
            production_sheet.update_cell(i, 3, f"完成 ({source_mark})")
            print(f"✅ 处理完成并已更新表格 (行 {i})")
            processed_count += 1

if __name__ == "__main__":
    # 为了保险，初始 limit 设为 5，你可以随意调大
    ultimate_pipeline(limit=5)
