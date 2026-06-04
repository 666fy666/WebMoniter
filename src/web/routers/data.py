"""Monitoring data API routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.storage.database import AsyncDatabase
from src.web.auth import check_login
from src.web.data_support import (
    _PLATFORM_LIST_SQL,
    _PLATFORM_LIST_SQL_HUYA_BASIC,
    _PLATFORM_SELECT,
    PLATFORM_CONFIG,
    PLATFORM_PRIMARY_KEY,
    VALID_PLATFORMS,
    _parse_weibo_created_at,
    _row_to_item,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/data/huya/images")
async def get_huya_images(request: Request, rooms: str = ""):
    """获取虎牙房间封面和头像 URL（需登录）。用于数据展示页异步加载图片。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    room_ids = [r.strip() for r in rooms.split(",") if r.strip()]
    if not room_ids:
        return JSONResponse({"data": {}})

    try:
        async with AsyncDatabase() as db:
            placeholders = ", ".join([f":r{i}" for i in range(len(room_ids))])
            params = {f"r{i}": rid for i, rid in enumerate(room_ids)}
            sql = f"SELECT room, room_pic, avatar_url FROM huya WHERE room IN ({placeholders})"
            rows = await db.execute_query(sql, params)

        data = {
            row[0]: {
                "room_pic": (row[1] or "").strip(),
                "avatar_url": (row[2] or "").strip(),
            }
            for row in rows
        }
        return JSONResponse({"data": data})
    except Exception as e:
        logger.error("获取虎牙图片 URL 失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/data/{platform}/{item_id}")
async def get_data_item(request: Request, platform: str, item_id: str):
    """按平台与主键 ID 获取单条监控数据（需登录）。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    if platform not in _PLATFORM_SELECT:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        async with AsyncDatabase() as db:
            _, sql = _PLATFORM_SELECT[platform]
            rows = await db.execute_query(sql, {"pk": item_id})

        if not rows:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        data = _row_to_item(platform, rows[0])
        return JSONResponse({"data": data})
    except Exception as e:
        logger.error("获取单条数据失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/data/{platform}")
async def get_table_data(
    request: Request,
    platform: str,
    page: int = 1,
    page_size: int = 100,
    include_media: bool = True,
    uid: str | None = None,
    room: str | None = None,
    id: str | None = None,
):
    """获取监控数据列表（需登录）。支持分页与按主键过滤。"""
    session_id = request.session.get("session_id")
    if not check_login(session_id):
        return JSONResponse({"error": "未授权"}, status_code=status.HTTP_401_UNAUTHORIZED)

    if platform not in VALID_PLATFORMS or platform not in _PLATFORM_LIST_SQL:
        logger.warning("请求了无效的数据平台: %r，有效平台: %s", platform, sorted(VALID_PLATFORMS))
        return JSONResponse(
            {
                "error": "无效的平台",
                "platform": platform,
                "valid_platforms": sorted(VALID_PLATFORMS),
            },
            status_code=400,
        )

    _, _, filter_param_name = PLATFORM_CONFIG[platform]
    filter_param = (
        uid if filter_param_name == "uid" else (room if filter_param_name == "room" else id)
    )

    try:
        async with AsyncDatabase() as db:
            where_clause = ""
            params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
            if filter_param:
                pk_col = PLATFORM_PRIMARY_KEY[platform]
                where_clause = f" WHERE {pk_col} = :filter_val"
                params["filter_val"] = filter_param

            table_name = PLATFORM_CONFIG[platform][0]
            count_sql = f"SELECT COUNT(*) FROM {table_name}{where_clause}"
            count_params = {k: v for k, v in params.items() if k in ("filter_val",)}
            count_result = await db.execute_query(count_sql, count_params if count_params else None)
            total = count_result[0][0] if count_result else 0

            base_sql = (
                _PLATFORM_LIST_SQL_HUYA_BASIC
                if platform == "huya" and not include_media
                else _PLATFORM_LIST_SQL[platform]
            )
            if platform == "weibo":
                sql = f"{_PLATFORM_LIST_SQL[platform]}{where_clause}"
                fetch_params = {k: v for k, v in params.items() if k == "filter_val"}
                rows = await db.execute_query(sql, fetch_params if fetch_params else None)
            else:
                sql = f"{base_sql}{where_clause} LIMIT :limit OFFSET :offset"
                rows = await db.execute_query(sql, params)

        data = [_row_to_item(platform, row) for row in rows]

        if platform == "weibo" and data:

            def sort_key(item: dict):
                dt = _parse_weibo_created_at(item.get("文本"))
                if dt is None:
                    return 0.0
                return dt.timestamp()

            data.sort(key=sort_key, reverse=True)
            offset = (page - 1) * page_size
            data = data[offset : offset + page_size]

        return JSONResponse(
            {
                "data": data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
            }
        )
    except Exception as e:
        logger.error("获取表数据失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/monitor-status/{platform}/{item_id}")
async def get_monitor_status_item(request: Request, platform: str, item_id: str):
    """按平台与主键 ID 获取单条监控状态（无需登录）。支持所有已持久化的平台。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        if platform not in _PLATFORM_SELECT:
            return JSONResponse({"error": "无效的平台"}, status_code=400)

        async with AsyncDatabase() as db:
            _, sql = _PLATFORM_SELECT[platform]
            rows = await db.execute_query(sql, {"pk": item_id})

        if not rows:
            return JSONResponse({"error": "未找到该资源"}, status_code=404)

        data = _row_to_item(platform, rows[0])

        return JSONResponse(
            {
                "success": True,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error("获取监控状态失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/monitor-status/{platform}")
async def get_monitor_status_by_platform(request: Request, platform: str):
    """按平台获取监控状态列表（无需登录）。支持所有已持久化的平台。"""
    if platform not in VALID_PLATFORMS:
        return JSONResponse({"error": "无效的平台"}, status_code=400)

    try:
        if platform not in _PLATFORM_LIST_SQL:
            return JSONResponse({"error": "无效的平台"}, status_code=400)

        async with AsyncDatabase() as db:
            rows = await db.execute_query(_PLATFORM_LIST_SQL[platform])

        data = [_row_to_item(platform, row) for row in rows]

        return JSONResponse(
            {
                "success": True,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error("获取监控状态失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/monitor-status")
async def get_monitor_status(request: Request):
    """获取全部监控任务状态（无需登录）。返回所有已持久化平台的聚合结果。"""

    try:
        async with AsyncDatabase() as db:
            all_data: dict[str, list[dict]] = {}

            for platform, base_sql in _PLATFORM_LIST_SQL.items():
                try:
                    rows = await db.execute_query(base_sql)
                    all_data[platform] = [_row_to_item(platform, row) for row in rows]
                except Exception as e:
                    logger.error("获取平台 %s 监控状态失败: %s", platform, e, exc_info=True)
                    all_data[platform] = []

        return JSONResponse(
            {
                "success": True,
                "data": all_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error("获取监控状态失败: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
