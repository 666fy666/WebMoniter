"""小茅预约（i茅台）任务模块

参考 only_for_happly/backup/imaotai.py：预约申购 + 小茅运领奖励。
配置格式：省份,城市,经度,纬度,设备id,token,MT-Token-Wap（小茅运可不填）
依赖：pycryptodome
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import json
import logging
import random
import re
import time

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

MT_R = "clips_OlU6TmFRag5rCXwbNAQ/Tz1SKlN8THcecBp/"
# 拟预约商品（itemCode -> 名称），可按需修改或后续从配置读取
RES_MAP = {
    "10941": "贵州茅台酒（甲辰龙年）",
    "10942": "贵州茅台酒（甲辰龙年）x2",
}


def _aes_cbc_encrypt(data: str, key: str, iv: str) -> str:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    padded = pad(data.encode("utf-8"), AES.block_size)
    return base64.b64encode(cipher.encrypt(padded)).decode("utf-8")


def _get_mt_version_from_store() -> str:
    try:
        r = requests.get(
            "https://apps.apple.com/cn/app/i%E8%8C%85%E5%8F%B0/id1600482450",
            timeout=10,
        )
        m = re.search(r'whats-new__latest__version">(.*?)</p>', r.text, re.S)
        if m:
            return m.group(1).replace("版本 ", "").replace("ç­æ¬¬ ", "").strip()
    except Exception as e:
        logger.warning("小茅预约：从 App Store 获取版本号失败 %s", e)
    return ""


def _get_map(mt_version: str, lng: str, lat: str) -> dict:
    """获取省份城市门店映射 p_c_map."""
    url = "https://static.moutai519.com.cn/mt-backend/xhr/front/mall/resource/get"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0_1 like Mac OS X)",
        "Referer": "https://h5.moutai519.com.cn/gux/game/main?appConfig=2_1_2",
        "Client-User-Agent": "iOS;16.0.1;Apple;iPhone 14 ProMax",
        "MT-R": MT_R,
        "Origin": "https://h5.moutai519.com.cn",
        "MT-APP-Version": mt_version,
        "MT-Request-ID": f"{int(time.time() * 1000)}{random.randint(1111111, 999999999)}{int(time.time() * 1000)}",
        "Accept-Language": "zh-CN,zh-Hans;q=1",
        "MT-Device-ID": f"{int(time.time() * 1000)}{random.randint(1111111, 999999999)}{int(time.time() * 1000)}",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "mt-lng": lng,
        "mt-lat": lat,
    }
    res = requests.get(url, headers=headers, timeout=15)
    data = res.json().get("data", {}).get("mtshops_pc", {})
    url_list = data.get("url")
    if not url_list:
        return {}
    r2 = requests.get(url_list, timeout=15)
    p_c_map = {}
    for k, v in (r2.json() or {}).items():
        province_name = v.get("provinceName")
        city_name = v.get("cityName")
        if not province_name or not city_name:
            continue
        if province_name not in p_c_map:
            p_c_map[province_name] = {}
        if city_name not in p_c_map[province_name]:
            p_c_map[province_name][city_name] = []
        p_c_map[province_name][city_name].append(k)
    return p_c_map


def _run_xiaomao_sync(
    token_line: str,
    mt_version: str,
    time_keys: str,
    p_c_map: dict,
) -> tuple[bool, str]:
    """同步执行单账号小茅预约。token_line 格式：省份,城市,经度,纬度,设备id,token,MT-Token-Wap"""
    lines = []
    try:
        parts = [p.strip() for p in token_line.split(",", 6)]
        if len(parts) < 7:
            return False, "配置格式错误，需要：省份,城市,经度,纬度,设备id,token,MT-Token-Wap"
        province, city, lng, lat, device_id, token, ck = parts
        if not token or not device_id:
            return False, "token 或设备id 为空"

        headers_session = {
            "mt-device-id": device_id,
            "mt-user-tag": "0",
            "accept": "*/*",
            "mt-network-type": "WIFI",
            "mt-token": token,
            "mt-bundle-id": "com.moutai.mall",
            "accept-language": "zh-Hans-CN;q=1",
            "mt-request-id": f"{int(time.time() * 1000)}",
            "mt-app-version": mt_version,
            "user-agent": "iPhone 14",
            "mt-r": MT_R,
            "mt-lng": lng,
            "mt-lat": lat,
        }
        # session
        r = requests.get(
            f"https://static.moutai519.com.cn/mt-backend/xhr/front/mall/index/session/get/{time_keys}",
            headers=headers_session,
            timeout=15,
        )
        sess_data = r.json().get("data", {})
        session_id = sess_data.get("sessionId")
        item_list = sess_data.get("itemList", [])
        item_codes = [item.get("itemCode") for item in item_list if item.get("itemCode")]
        if not session_id:
            return False, "获取 session 失败，请检查 token 是否有效"

        # user info
        headers_user = {
            "MT-User-Tag": "0",
            "Accept": "*/*",
            "MT-Network-Type": "WIFI",
            "MT-Token": token,
            "MT-Bundle-ID": "com.moutai.mall",
            "Accept-Language": "zh-Hans-CN;q=1, en-CN;q=0.9",
            "MT-Request-ID": f"{int(time.time() * 1000)}",
            "MT-APP-Version": mt_version,
            "User-Agent": "iOS;16.0.1;Apple;iPhone 14 ProMax",
            "MT-R": MT_R,
            "MT-Device-ID": device_id,
            "mt-lng": lng,
            "mt-lat": lat,
        }
        ru = requests.get(
            "https://app.moutai519.com.cn/xhr/front/user/info",
            headers=headers_user,
            timeout=15,
        )
        user_data = ru.json().get("data", {})
        user_id = user_data.get("userId")
        user_name = user_data.get("userName", "")
        mobile = user_data.get("mobile", "")
        if not user_id:
            return False, "用户 token 失效，请重新登录"
        lines.append(f"{user_name}_{mobile} 开始任务")

        # 预约
        shop_ids = p_c_map.get(province, {}).get(city, [])
        for item_code in item_codes:
            name = RES_MAP.get(str(item_code))
            if not name:
                continue
            # get_shop_item
            shop_id = None
            rshop = requests.get(
                f"https://static.moutai519.com.cn/mt-backend/xhr/front/mall/shop/list/slim/v3/{session_id}/{province}/{item_code}/{time_keys}",
                headers=headers_session,
                timeout=15,
            )
            shops = (rshop.json().get("data") or {}).get("shops", [])
            for shop in shops:
                if shop.get("shopId") not in shop_ids:
                    continue
                if str(item_code) in str(shop):
                    shop_id = shop.get("shopId")
                    break
            if not shop_id:
                lines.append(f"{item_code}_{name}: 无可预约门店")
                continue
            # mt_add
            payload = {
                "itemInfoList": [{"count": 1, "itemId": str(item_code)}],
                "sessionId": session_id,
                "userId": str(user_id),
                "shopId": str(shop_id),
            }
            act_param = _aes_cbc_encrypt(
                json.dumps(payload),
                "qbhajinldepmucsonaaaccgypwuvcjaa",
                "2018534749963515",
            )
            payload["actParam"] = act_param
            add_headers = {
                "User-Agent": "iPhone 14",
                "MT-Token": token,
                "MT-Network-Type": "WIFI",
                "MT-User-Tag": "0",
                "MT-R": MT_R,
                "MT-K": f"{int(time.time() * 1000)}",
                "MT-Info": "028e7f96f6369cafe1d105579c5b9377",
                "MT-APP-Version": mt_version,
                "MT-Request-ID": f"{int(time.time() * 1000)}",
                "Accept-Language": "zh-Hans-CN;q=1",
                "MT-Device-ID": device_id,
                "MT-Bundle-ID": "com.moutai.mall",
                "mt-lng": lng,
                "mt-lat": lat,
            }
            radd = requests.post(
                "https://app.moutai519.com.cn/xhr/front/mall/reservation/add",
                headers=add_headers,
                json=payload,
                timeout=15,
            )
            j = radd.json()
            if j.get("code") == 2000:
                desc = (j.get("data") or {}).get("successDesc", "成功")
                lines.append(f"{item_code}_{name}: {desc}")
            else:
                lines.append(f"{item_code}_{name}: 申购失败 {j.get('message', '')}")

        if ck and ck.strip() and ck not in ("''", '""'):
            cookies = {
                "MT-Device-ID-Wap": device_id,
                "MT-Token-Wap": ck,
                "YX_SUPPORT_WEBP": "1",
            }
            h = {
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_2_1 like Mac OS X)",
                "Referer": "https://h5.moutai519.com.cn/gux/game/main?appConfig=2_1_2",
                "MT-R": MT_R,
                "Origin": "https://h5.moutai519.com.cn",
                "MT-APP-Version": mt_version,
                "MT-Request-ID": f"{int(time.time() * 1000)}",
                "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                "MT-Device-ID": device_id,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "mt-lng": lng,
                "mt-lat": lat,
            }
            rw = requests.post(
                "https://h5.moutai519.com.cn/game/isolationPage/getUserEnergyAward",
                cookies=cookies,
                headers=h,
                json={},
                timeout=15,
            )
            if "无法领取奖励" in rw.text:
                lines.append("小茅运: " + (rw.json().get("message") or "无法领取"))
            else:
                lines.append("小茅运: 领取奖励成功")

        return True, "\n".join(lines)
    except Exception as e:
        logger.exception("小茅预约单账号执行异常")
        return False, str(e)


async def run_xiaomao_checkin_once() -> None:
    """执行一次小茅预约（多账号），并接入统一推送。"""
    from dataclasses import dataclass

    @dataclass
    class XiaomaoConfig:
        enable: bool
        token: str
        tokens: list[str]
        mt_version: str
        time: str
        push_channels: list[str]

        @classmethod
        def from_app_config(cls, config: AppConfig) -> XiaomaoConfig:
            tokens: list[str] = getattr(config, "xiaomao_tokens", None) or []
            single = (getattr(config, "xiaomao_token", None) or "").strip()
            if not tokens and single:
                tokens = [single]
            return cls(
                enable=getattr(config, "xiaomao_enable", False),
                token=single,
                tokens=tokens,
                mt_version=(getattr(config, "xiaomao_mt_version", None) or "").strip(),
                time=(getattr(config, "xiaomao_time", None) or "09:00").strip() or "09:00",
                push_channels=getattr(config, "xiaomao_push_channels", None) or [],
            )

        def validate(self) -> bool:
            if not self.enable:
                return False
            effective = self.tokens or ([self.token] if self.token else [])
            if not effective or not any(t.strip() for t in effective):
                logger.error("小茅预约配置不完整，缺少 token 或 tokens")
                return False
            return True

    app_config = get_config(reload=True)
    cfg = XiaomaoConfig.from_app_config(app_config)
    if not cfg.validate():
        return

    effective = [t.strip() for t in cfg.tokens if t.strip()]
    if not effective and cfg.token:
        effective = [cfg.token.strip()]
    mt_version = cfg.mt_version or _get_mt_version_from_store()
    if not mt_version:
        logger.error("小茅预约：未配置 mt_version 且无法从 App Store 获取")
        return

    time_keys = str(int(time.mktime(datetime.date.today().timetuple())) * 1000)
    # 用第一个账号的经纬度拉取门店地图
    first_line = effective[0]
    parts = first_line.split(",", 6)
    lng, lat = "121.5", "30.0"
    if len(parts) >= 4:
        lng, lat = parts[2].strip(), parts[3].strip()
    try:
        p_c_map = _get_map(mt_version, lng, lat)
    except Exception as e:
        logger.warning("小茅预约：获取门店地图失败 %s，继续执行", e)
        p_c_map = {}

    logger.info("小茅预约：开始执行（共 %d 个账号）", len(effective))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="小茅预约：",
            channel_names=cfg.push_channels or None,
        )
        for idx, token_line in enumerate(effective):
            try:
                ok, msg = await asyncio.to_thread(
                    _run_xiaomao_sync,
                    token_line,
                    mt_version,
                    time_keys,
                    p_c_map,
                )
            except Exception as e:
                logger.error("小茅预约：第 %d 个账号异常: %s", idx + 1, e)
                ok, msg = False, str(e)
            if push_manager and not is_in_quiet_hours(app_config):
                title = "小茅预约成功" if ok else "小茅预约失败"
                try:
                    await push_manager.send_news(
                        title=title,
                        description=msg,
                        to_url="https://app.moutai519.com.cn",
                        picurl="",
                        btntxt="打开",
                    )
                except Exception as exc:
                    logger.error("小茅预约：推送失败 %s", exc)
        if push_manager:
            await push_manager.close()
    logger.info("小茅预约：结束（共处理 %d 个账号）", len(effective))


def _get_xiaomao_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "xiaomao_time", "09:00") or "09:00")
    return {"minute": minute, "hour": hour}


register_task("xiaomao_checkin", run_xiaomao_checkin_once, _get_xiaomao_trigger_kwargs)
