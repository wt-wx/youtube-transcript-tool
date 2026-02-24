from src.core.google_api import GoogleClient
from src.core.config import Config

def check_status():
    google = GoogleClient()
    sheet = google.get_production_sheet()
    records = sheet.get_all_values()
    
    status_counts = {}
    stuck_videos = []
    
    for i, row in enumerate(records[1:], start=2):
        status = row[2] if len(row) > 2 else "EMPTY"
        transcript = row[4] if len(row) > 4 else ""
        
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # 寻找卡住的 HK 任务
        if status == "音频已就绪" and not transcript:
            stuck_videos.append(f"Row {i}: {row[1]}")
            
    print("\n--- 任务状态统计 ---")
    for status, count in status_counts.items():
        print(f"{status}: {count} 条")
        
    if stuck_videos:
        print("\n--- HK 节点卡住的任务 (前 5 条) ---")
        for v in stuck_videos[:5]:
            print(v)
    else:
        print("\n没有发现 HK 节点卡住的任务")

if __name__ == "__main__":
    check_status()
