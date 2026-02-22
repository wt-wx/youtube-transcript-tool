# Google OAuth Scopes & Sheets API Troubleshooting
Created: 2026-02-22

## 核心发现
当 Python 脚本（如 gspread）尝试访问从未授权过的 API Scope（如 Spreadsheets）时，Google 不会自动提示，而是直接返回 `missing scopes` 错误。

## 关键症状
- 日志报错：`Not all requested scopes were granted by the authorization server`
- 现象：`token.json` 已存在但回填数据失败。

## 修复路径
1. **GCP Console 设置**：
   - 启用 **Google Sheets API**。
   - 在 **OAuth 同意屏幕 (OAuth consent screen)** -> **数据访问 (Data Access)** 中，手动添加 `https://www.googleapis.com/auth/spreadsheets`。
2. **本地客户端刷新**：
   - **必须物理删除** 旧的 `token.json`。
   - 重新运行 `auth_setup.py`（Desktop App 类型）。
   - **交互关键**：在浏览器授权页面，必须手动勾选“查看和编辑所有表格”的复选框。
3. **分发**：更新后的 `token.json` 需同步至所有节点。

## 最佳实践
Scopes 变更后，仅刷新旧 Token 无效，必须重新走全量授权流程。
