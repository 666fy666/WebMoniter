"""天气推送任务

参考 only_for_happly/weather.py：
- 使用 city_code 调用 http://t.weather.itboy.net/api/weather/city/{city_code}
- 推送今日天气详情与未来 7 日简要预报

本任务改造点：
- city_code 从 config.yml 的 weather.city_code 读取
- 接入统一推送与免打扰逻辑
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

WEATHER_API = "http://t.weather.itboy.net/api/weather/city/{city_code}"


@dataclass
class WeatherConfig:
    enable: bool
    city_code: str
    time: str
    push_channels: list[str]

    @classmethod
    def from_app_config(cls, config: AppConfig) -> WeatherConfig:
        return cls(
            enable=getattr(config, "weather_enable", False),
            city_code=(getattr(config, "weather_city_code", None) or "").strip(),
            time=(getattr(config, "weather_time", None) or "07:30").strip() or "07:30",
            push_channels=getattr(config, "weather_push_channels", None) or [],
        )

    def validate(self) -> bool:
        if not self.enable:
            logger.debug("天气推送未启用，跳过执行")
            return False
        if not self.city_code:
            logger.error("天气推送配置不完整：weather.city_code 不能为空")
            return False
        return True


def _fetch_weather(city_code: str) -> dict[str, Any] | None:
    try:
        resp = requests.get(
            WEATHER_API.format(city_code=city_code),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != 200:
            logger.error("天气接口返回异常状态：%s", data)
            return None
        return data
    except Exception as exc:  # pragma: no cover - 防御性
        logger.error("获取天气数据失败：%s", exc)
        return None


def _build_message(data: dict[str, Any]) -> str:
    city = data.get("cityInfo", {}).get("city", "")
    today = data.get("data", {}).get("forecast", [{}])[0]
    d = data.get("data", {})

    lines: list[str] = []
    lines.append(f"城市：{city}")
    lines.append(
        "日期：{ymd} {week}".format(
            ymd=today.get("ymd", ""),
            week=today.get("week", ""),
        )
    )
    lines.append(
        "天气：{type}".format(
            type=today.get("type", ""),
        )
    )
    lines.append(
        "温度：{high} {low}".format(
            high=today.get("high", ""),
            low=today.get("low", ""),
        )
    )
    lines.append(f"湿度：{d.get('shidu', '')}")
    lines.append(f"空气质量：{d.get('quality', '')}")
    lines.append(f"PM2.5：{d.get('pm25', '')}")
    lines.append(f"PM10：{d.get('pm10', '')}")
    lines.append(
        "风力风向：{fx} {fl}".format(
            fx=today.get("fx", ""),
            fl=today.get("fl", ""),
        )
    )
    lines.append(f"感冒指数：{d.get('ganmao', '')}")
    lines.append(f"温馨提示：{today.get('notice', '')}")
    lines.append(f"更新时间：{data.get('time', '')}")

    # 7 日预报
    forecast = d.get("forecast", [])[:7]
    if forecast:
        lines.append("")
        lines.append("未来 7 日预报：")
        for day in forecast:
            line = (
                f"{day.get('ymd', '')} {day.get('week', '')} "
                f"{day.get('type', '')} "
                f"{day.get('low', '')}/{day.get('high', '')} "
                f"{day.get('notice', '')}"
            )
            lines.append(line)

    return "\n".join(lines)


async def run_weather_push_once() -> None:
    """执行一次天气推送任务。"""
    app_cfg = get_config(reload=True)
    cfg = WeatherConfig.from_app_config(app_cfg)
    if not cfg.validate():
        return

    data = _fetch_weather(cfg.city_code)
    if not data:
        return

    msg = _build_message(data)
    title = f"今日天气：{data.get('cityInfo', {}).get('city', '')}"

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push: UnifiedPushManager | None = await build_push_manager(
            app_cfg.push_channel_list,
            session,
            logger,
            init_fail_prefix="天气推送：",
            channel_names=cfg.push_channels or None,
        )
        if push and not is_in_quiet_hours(app_cfg):
            try:
                city_info = data.get("cityInfo", {})
                today = (data.get("data", {}) or {}).get("forecast", [{}])[0]
                await push.send_news(
                    title=title or "天气推送",
                    description=msg,
                    to_url="https://t.weather.itboy.net/",
                    picurl="",
                    btntxt="查看详情",
                    event_type="weather",
                    event_data={
                        "city": city_info.get("city"),
                        "date": today.get("ymd"),
                        "week": today.get("week"),
                        "weather_type": today.get("type"),
                        "high": today.get("high"),
                        "low": today.get("low"),
                    },
                )
            except Exception as exc:  # pragma: no cover
                logger.error("天气推送：发送失败：%s", exc, exc_info=True)
            finally:
                await push.close()


def _get_weather_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(getattr(config, "weather_time", "07:30") or "07:30")
    return {"minute": minute, "hour": hour}


register_task("weather_push", run_weather_push_once, _get_weather_trigger_kwargs)
