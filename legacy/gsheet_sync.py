import gspread
from oauth2client.service_account import ServiceAccountCredentials
from youtube_transcript_api import YouTubeTranscriptApi

# 1. Google Sheets 授权设置
# 需要在 Google Cloud 下载服务账号 JSON 凭据
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# 2. 打开表格
spreadsheet = client.open("YouTube_Blogger_Automation")
production_sheet = spreadsheet.worksheet("Production")

def batch_fill_transcripts(limit=10):
    # 获取所有数据
    records = production_sheet.get_all_values()
    
    # 实例化 API
    api = YouTubeTranscriptApi()
    
    processed_count = 0
    for i, row in enumerate(records[1:], start=2): # 跳过表头
        if processed_count >= limit:
            print(f"已达到本次测试上限（{limit} 条），停止处理。")
            break
            
        # 注意：这里假设 B 列是 Video ID (index 1)，E 列是 Transcript (index 4)
        video_id = row[1] if len(row) > 1 else ""   # B 列: Video ID
        transcript_cell = row[4] if len(row) > 4 else "" # E 列: Transcript
        
        # 如果 B 列有 ID 且 E 列是空的，则执行抓取
        if video_id and not transcript_cell:
            try:
                processed_count += 1
                print(f"[{processed_count}/{limit}] 正在抓取视频 {video_id} 的字幕...")
                # 抓取字幕（优先尝试中文，不行再抓英文）
                # 使用新版 API: 实例化后调用 fetch 并使用 to_raw_data()
                transcript_obj = api.fetch(video_id, languages=['zh-Hans', 'zh-Hant', 'en'])
                srt = transcript_obj.to_raw_data()
                
                # 合并文本
                full_text = " ".join([t['text'] for t in srt])
                
                # 写回表格 E 列
                production_sheet.update_cell(i, 5, full_text)
                print(f"✅ 成功填入行 {i}")
                
            except Exception as e:
                print(f"❌ 无法获取视频 {video_id} 的字幕: {str(e)}")
                # 写入 C 列 (index 2) "字幕不可用"
                production_sheet.update_cell(i, 3, "字幕不可用")

if __name__ == "__main__":
    # 你可以在这里修改 limit 的值，例如改为 20
    batch_fill_transcripts(limit=10)
