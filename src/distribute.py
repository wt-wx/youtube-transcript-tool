# distribute.py – GOS‑Ingestor 内容分发适配器
# 说明: 该模块提供将已润色的内容自动发布到 Blogger.com 与 WordPress.com 的入口函数。
# 本模块直接调用官方分发 REST API，负责外部平台的交付。

import os
import json
import base64
import urllib.request
from typing import Dict, Any

# 本项目已提供的多源连接器，用于写入 Supabase（可选）
from core.brain.agent.tools.pg_tool import query_postgres

from googleapiclient.discovery import build
from src.core.google_api import GoogleClient
from src.core.config import Config

# ------------------- 分发函数 -------------------
def publish_to_blogger(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """将内容发布到 Blogger.com。
    参数:
        post_data: 必须包含 `title`、`content`（HTML）以及可选 `labels` 列表。
    返回:
        API 响应的标准化 dict。
    """
    try:
        # 获取封装好的 GoogleAuth 或者 Credentials
        client = GoogleClient()
        creds = client._user_creds or client._creds
        
        blogger_service = build('blogger', 'v3', credentials=creds)
        blog_id = os.environ.get("BLOGGER_BLOG_ID")
        
        if not blog_id:
            return {"status": "error", "error": "Missing BLOGGER_BLOG_ID in environment variables"}
            
        body = {
            "title": post_data.get("title", "Untitled Post"),
            "content": post_data.get("content", ""),
            "labels": post_data.get("labels", [])
        }
        
        # 实际向 Blogger 提交资源
        posts = blogger_service.posts()
        res = posts.insert(blogId=blog_id, body=body, isDraft=False).execute()
        
        return {"status": "ok", "post_id": res.get("id"), "url": res.get("url")}
        
    except Exception as e:
        return {"status": "error", "error": f"Blogger API Error: {str(e)}"}


def publish_to_wordpress(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """将内容发布到 WordPress.com（或自托管 WP）。
    参数同上。
    返回同上。
    """
    try:
        wp_url = os.environ.get("WORDPRESS_URL")
        wp_user = os.environ.get("WORDPRESS_USER")
        wp_pass = os.environ.get("WORDPRESS_APP_PASSWORD")
        
        if not all([wp_url, wp_user, wp_pass]):
            return {"status": "error", "error": "Missing WordPress configuration (URL, USER, or APP_PASSWORD)"}

        # 组织请求体 (WP API)
        payload = {
            "title": post_data.get("title", "Untitled Post"),
            "content": post_data.get("content", ""),
            "status": "publish",  # draft, publish
            "categories": post_data.get("categories", []),
            "tags": post_data.get("tags", [])
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{wp_url.rstrip('/')}/posts", data=data)
        
        # Basic Auth 准备
        auth_string = f"{wp_user}:{wp_pass}"
        base64_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        req.add_header("Authorization", f"Basic {base64_auth}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0")
        
        # 使用原生 urllib 执行请求以规避额外的 requests 库依赖
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            res_data = json.loads(res_body.decode("utf-8"))
            
            return {
                "status": "ok", 
                "post_id": res_data.get("id"), 
                "url": res_data.get("link")
            }
            
    except Exception as e:
        return {"status": "error", "error": f"WordPress API Error: {str(e)}"}

# ------------------- 高层调用示例 -------------------
def distribute(content: Dict[str, Any], targets: list = None) -> Dict[str, Any]:
    """统一分发入口，支持一次性向多个平台发布。
    参数:
        content: 包含 `title`、`content`、`labels` 等字段的字典。
        targets: 目标平台列表，例如 ["blogger", "wordpress"]，默认全部。
    返回:
        各平台的发布结果字典。
    """
    if targets is None:
        targets = ["blogger", "wordpress"]
    results = {}
    for t in targets:
        if t == "blogger":
            results[t] = publish_to_blogger(content)
        elif t == "wordpress":
            results[t] = publish_to_wordpress(content)
        else:
            results[t] = {"status": "error", "error": f"unsupported platform {t}"}
    return results
