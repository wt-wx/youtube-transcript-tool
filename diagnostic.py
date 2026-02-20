import os
from src.core.config import Config
from src.core.google_api import GoogleClient

def diagnostic():
    print("🔍 正在启动环境诊断 (v2.0)...")
    
    # 1. 检查凭据文件
    if not os.path.exists(Config.CREDENTIALS_FILE):
        print(f"❌ 错误：未找到凭据文件 ({Config.CREDENTIALS_FILE})。")
        return
    print(f"✅ 找到凭据文件: {Config.CREDENTIALS_FILE}")

    # 2. 检查 Google 客户端
    try:
        google = GoogleClient()
        if google._user_creds:
            print("✅ 个人号 OAuth 授权 (token.json) 解析成功")
        else:
            print("✅ 服务账号凭据解析成功")
            print(f"📧 服务账号 Email: {google._creds.service_account_email}")
    except Exception as e:
        print(f"❌ 凭据解析失败: {e}")
        return

    # 3. 检查 Sheets API
    try:
        production_sheet = google.get_production_sheet()
        print(f"✅ Google Sheets 连接成功: {Config.SPREADSHEET_NAME}")
    except Exception as e:
        print(f"❌ Google Sheets 连接失败。")
        print(f"   错误详情: {e}")

    # 4. 检查 Drive API
    try:
        drive_service = google.get_drive_service()
        if Config.DRIVE_FOLDER_ID:
            folder = drive_service.files().get(
                fileId=Config.DRIVE_FOLDER_ID, 
                fields='name, capabilities'
            ).execute()
            print(f"✅ Google Drive 文件夹识别成功: {folder.get('name')}")
            if folder.get('capabilities', {}).get('canAddChildren'):
                print("✅ 权限验证成功：具有写入权限")
            else:
                print("❌ 警告：没有写入权限 (请设为“编辑者”)")
        else:
            print("ℹ️ 未设置 DRIVE_FOLDER_ID，将上传到根目录")
            drive_service.files().list(pageSize=1).execute()
            print("✅ Google Drive API 验证成功")
    except Exception as e:
        print(f"❌ Google Drive API 验证失败: {e}")

    print("\n🏁 诊断结束。")

if __name__ == "__main__":
    diagnostic()
