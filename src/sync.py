# sync.py – GOS‑Ingestor 双向同步工具
# 说明: 该模块提供与 Google Sheets 与 Supabase (PostgreSQL) 双向同步的真实连接组件。
# 采用核心的 `pg_tool.query_postgres` 进行数据库层面交互，
# 采用 `google_api.py` 的 GoogleClient 单例提供 gspread 生产表控制权。

import json
from typing import List, Dict, Any

# 本项目已提供的多源连接器
from core.brain.agent.tools.pg_tool import query_postgres

# 引入项目自带的 GoogleClient 单例封装
from src.core.google_api import GoogleClient
from src.core.config import Config

# ------------------- Google Sheets 执行层 -------------------
def _get_worksheet():
    """获取 gspread 的 worksheet 实例"""
    client = GoogleClient()
    return client.get_production_sheet()


# ------------------- 同步函数 -------------------
def sync_to_sheets(table_name: str, range_name: str = "A1") -> Dict[str, Any]:
    """将 PostgreSQL 表数据写入 Google Sheets。
    步骤:
        1. 从 Supabase（或本地 PG）读取完整表数据。
        2. 将结果转为二维数组（list of list），写入指定 sheet。
    参数:
        table_name: 数据库表名
        range_name: 起始单元格（默认 A1）
    返回:
        Google Sheets API 响应的标准化 dict。
    """
    try:
        # 读取数据（默认使用 supabase 连接）
        sql = f"SELECT * FROM {table_name};"
        raw = query_postgres(sql, connection_id="supabase")
        data = json.loads(raw)
        
        if isinstance(data, dict) and data.get("error"):
            return {"status": "error", "error": data["error"]}

        # 转换为二维数组（首行为列名）
        if not data:
            rows = []
        else:
            header = list(data[0].keys())
            # 格式化数据，处理可能引起 Google Sheets 报错的对象 (如 dict / list)
            rows = [header] + [
                [str(v) if isinstance(v, (dict, list)) else v for v in item.values()] 
                for item in data
            ]

        # 写入真实 Google Sheet
        worksheet = _get_worksheet()
        # 清空原有数据
        worksheet.clear()
        # 更新新数据
        worksheet.update(values=rows, range_name=range_name)
        
        return {"status": "ok", "message": f"Successfully updated sheet {Config.SHEET_NAME}", "rows_written": len(rows) - 1 if rows else 0}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


def sync_to_supabase(table_name: str) -> Dict[str, Any]:
    """将 Google Sheets 数据写入 Supabase（PostgreSQL）表。
    步骤:
        1. 从 Google Sheets 读取二维数组。
        2. 解析为字典列表并生成 INSERT/UPDATE 语句。
    参数:
        table_name: 数据库表名
    返回:
        数据库执行结果的标准化 dict。
    """
    try:
        # 读取真实 Google Sheet
        worksheet = _get_worksheet()
        rows = worksheet.get_all_values()
        
        if not rows or len(rows) < 2:
            return {"status": "ok", "message": "empty sheet or header only"}
            
        header, *values = rows
        
        # 简单的 upsert（INSERT … ON CONFLICT DO UPDATE）
        placeholders = ", ".join(["%s"] * len(header))
        columns = ", ".join([f'"{col}"' for col in header]) # 避免由保留字引发的语法错
        conflict_target = f'"{header[0]}"'  # 假设第一列为唯一键
        
        set_clause = ", ".join([f'"{col}"=EXCLUDED."{col}"' for col in header[1:]])
        
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) " \
              f"ON CONFLICT ({conflict_target}) DO UPDATE SET {set_clause};"
              
        # 批量执行
        results = []
        for row in values:
            # 数据清洗，确保没有完全空值的行提交
            if not any(row):
                continue
            # 补齐长度以防越界
            padded_row = row + [""] * (len(header) - len(row))
            res = query_postgres(sql, params=padded_row, connection_id="supabase")
            results.append(json.loads(res))
            
        return {"status": "ok", "rows_processed": len(results), "details": results}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}
