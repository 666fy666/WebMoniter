"""服务器到期检查与自动续费（参考 Rainyun-Qiandao server/manager.py）"""

import logging
from datetime import datetime

from tasks.rainyun.api_client import RainyunAPI, RainyunAPIError
from tasks.rainyun.config_adapter import RainyunRunConfig

logger = logging.getLogger(__name__)
DEFAULT_RENEW_COST_7_DAYS = 2258


def check_and_renew(config: RainyunRunConfig) -> dict:
    """检查服务器到期并执行自动续费，返回结果摘要"""
    result = {
        "points": 0,
        "servers": [],
        "renewed": [],
        "warnings": [],
        "points_warning": None,
    }
    if not config.rainyun_api_key:
        return result
    prefix = f"用户 {config.display_name} " if config.display_name else ""
    try:
        api = RainyunAPI(config.rainyun_api_key, config)
        result["points"] = api.get_user_points()
        server_ids = api.get_server_ids()
        if not server_ids:
            return result
        for sid in server_ids:
            try:
                detail = api.get_server_detail(sid)
                server_data = detail.get("Data", {}) if isinstance(detail, dict) else {}
                expired_at = server_data.get("ExpDate", 0)
                if not expired_at or expired_at <= 0:
                    continue
                expired_dt = datetime.fromtimestamp(expired_at)
                days_remaining = max(0, (expired_dt - datetime.now()).days)
                egg_type = server_data.get("EggType") or {}
                egg_info = egg_type.get("egg") if isinstance(egg_type, dict) else {}
                egg_info = egg_info or {}
                server_name = egg_info.get("title", f"游戏云-{sid}")
                renew_price_map = detail.get("RenewPointPrice") or {}
                raw_price = renew_price_map.get(7) or renew_price_map.get("7")
                try:
                    renew_price = (
                        int(raw_price) if raw_price is not None else DEFAULT_RENEW_COST_7_DAYS
                    )
                except (ValueError, TypeError):
                    renew_price = DEFAULT_RENEW_COST_7_DAYS
                server_status = {
                    "id": sid,
                    "name": server_name,
                    "expired": expired_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "days_remaining": days_remaining,
                    "renew_price": renew_price,
                    "renewed": False,
                }
                if days_remaining <= config.renew_threshold_days:
                    if config.renew_product_ids and sid not in config.renew_product_ids:
                        result["warnings"].append(f"{server_name} 即将到期，但不在续费白名单中")
                        server_status["skip_reason"] = "⏭ 不在白名单"
                    elif not config.auto_renew:
                        result["warnings"].append(f"{server_name} 即将到期，但自动续费已关闭")
                        server_status["skip_reason"] = "⏭ 自动续费关闭"
                    elif result["points"] >= renew_price:
                        try:
                            api.renew_server(sid, 7)
                            result["points"] -= renew_price
                            result["renewed"].append(server_name)
                            server_status["renewed"] = True
                            logger.info("%s✅ %s 续费成功", prefix, server_name)
                        except RainyunAPIError as e:
                            result["warnings"].append(f"{server_name} 续费失败: {e}")
                    else:
                        result["warnings"].append(f"积分不足！{server_name} 需要 {renew_price}")
                        server_status["skip_reason"] = "⏭ 积分不足"
                else:
                    server_status["skip_reason"] = f"⏭ 未达阈值 {config.renew_threshold_days} 天"
                result["servers"].append(server_status)
            except RainyunAPIError as e:
                logger.warning("%s获取服务器 %d 详情失败: %s", prefix, sid, e)
        whitelist = [
            s for s in result["servers"] if s["days_remaining"] <= config.renew_threshold_days
        ]
        if config.renew_product_ids:
            whitelist = [s for s in whitelist if s["id"] in config.renew_product_ids]
        if whitelist and result["points"] < sum(s["renew_price"] for s in whitelist):
            total_needed = sum(s["renew_price"] for s in whitelist)
            shortage = total_needed - result["points"]
            days_needed = (shortage // 500) + (1 if shortage % 500 else 0)
            result["points_warning"] = {
                "current": result["points"],
                "needed": total_needed,
                "shortage": shortage,
                "servers_count": len(whitelist),
                "days_to_recover": days_needed,
            }
    except RainyunAPIError as e:
        logger.error("%s服务器检查失败: %s", prefix, e)
        result["warnings"].append(str(e))
    return result


def generate_report(result: dict, config: RainyunRunConfig) -> str:
    """生成服务器状态报告（与 Jielumoon/Rainyun-Qiandao server/manager.py 保持一致）"""
    lines = ["\n\n━━━━━━ 服务器状态 ━━━━━━", f"💰 当前积分: {result['points']}"]
    if result.get("points_warning"):
        pw = result["points_warning"]
        lines.extend(
            [
                "",
                "🚨 积分预警 🚨",
                f"  续费 {pw['servers_count']} 台服务器需要: {pw['needed']} 积分",
                f"  当前积分: {pw['current']}",
                f"  缺口: {pw['shortage']} 积分",
                f"  建议: 连续签到 {pw['days_to_recover']} 天可补足",
            ]
        )
    if result["servers"]:
        lines.append("")
        for s in result["servers"]:
            status = "✅ 已续费" if s.get("renewed") else ""
            skip = s.get("skip_reason", "")
            emoji = "🔴" if s["days_remaining"] <= 3 else "🟡" if s["days_remaining"] <= 7 else "🟢"
            lines.append(f"🖥️ {s['name']} (续费: {s['renew_price']}积分/7天)")
            lines.append(
                f"   {emoji} 剩余 {s['days_remaining']} 天 ({s['expired']}) {status} {skip}".strip()
            )
    else:
        lines.append("")
        lines.append("📭 无服务器")
    if result["renewed"]:
        lines.append("")
        lines.append(f"🎉 本次续费: {', '.join(result['renewed'])}")
    if result["warnings"]:
        lines.append("")
        lines.append("⚠️ 警告:")
        for w in result["warnings"]:
            lines.append(f"  - {w}")
    return "\n".join(lines)
