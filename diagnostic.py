import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

def diagnostic():
    print("🔍 正在启动环境诊断...")
    
    # 1. 检查凭据文件
    creds_file = os.getenv('CREDENTIALS_FILE', 'credentials.json')
    if not os.path.exists(creds_file):
        print("❌ 错误：未找到凭据文件 (credentials.json)。请先上传。")
        return
    print(f"✅ 找到凭据文件: {creds_file}")

    # 2. 尝试授权
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        print("✅ 服务账号凭据解析成功")
        print(f"📧 服务账号 Email: {creds.service_account_email}")
    except Exception as e:
        print(f"❌ 凭据解析失败: {e}")
        return

    # 3. 检查 Sheets API
    try:
        gc = gspread.authorize(creds)
        sheet_name = os.getenv('SPREADSHEET_NAME', 'YouTube_Blogger_Automation')
        spreadsheet = gc.open(sheet_name)
        print(f"✅ Google Sheets 连接成功: {sheet_name}")
    except Exception as e:
        print(f"❌ Google Sheets 连接失败。请确保：")
        print("   1. 已在 GCP 开启 Sheets API")
        print(f"   2. 已将表格共享给 {creds.service_account_email}")
        print(f"   错误详情: {e}")

    # 4. 检查 Drive API 和文件夹权限
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        folder_id = os.getenv('DRIVE_FOLDER_ID', '')
        if folder_id:
            folder = drive_service.files().get(fileId=folder_id, fields='name, capabilities').execute()
            print(f"✅ Google Drive 文件夹识别成功: {folder.get('name')}")
            if folder.get('capabilities', {}).get('canAddChildren'):
                print("✅ 权限验证成功：服务账号具有写入权限")
            else:
                print("❌ 警告：服务账号对该文件夹没有写入权限 (请设为“编辑者”)")
        else:
            print("ℹ️ 未设置 DRIVE_FOLDER_ID，将上传到根目录")
            # 尝试列出文件以验证 API
            drive_service.files().list(pageSize=1).execute()
            print("✅ Google Drive API 验证成功")
    except Exception as e:
        print(f"❌ Google Drive API 验证失败。请确保：")
        print("   1. 已在 GCP 开启 Drive API")
        print(f"   2. 已将文件夹共享给 {creds.service_account_email}")
        print(f"   错误详情: {e}")

    print("\n🏁 诊断结束。如果以上都是绿色，你的 LA 节点就可以跑了！")

if __name__ == "__main__":
    diagnostic()
