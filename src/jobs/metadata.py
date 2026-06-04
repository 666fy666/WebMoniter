"""任务展示元数据。"""

JOB_DESCRIPTIONS = {
    "huya_monitor": "虎牙直播状态监控",
    "weibo_monitor": "微博动态监控",
    "bilibili_monitor": "哔哩哔哩动态+直播监控",
    "douyin_monitor": "抖音直播状态监控",
    "douyu_monitor": "斗鱼直播状态监控",
    "xhs_monitor": "小红书动态监控",
    "log_cleanup": "日志文件清理",
    "ikuuu_checkin": "ikuuu 每日签到",
    "tieba_checkin": "百度贴吧签到",
    "weibo_chaohua_checkin": "微博超话签到",
    "rainyun_checkin": "雨云签到",
    "enshan_checkin": "恩山论坛签到",
    "fg_checkin": "富贵论坛签到",
    "aliyun_checkin": "阿里云盘签到",
    "smzdm_checkin": "什么值得买签到",
    "zdm_draw": "值得买每日抽奖",
    "tyyun_checkin": "天翼云盘签到",
    "miui_checkin": "小米社区签到",
    "iqiyi_checkin": "爱奇艺签到",
    "lenovo_checkin": "联想乐豆签到",
    "lbly_checkin": "丽宝乐园签到",
    "pinzan_checkin": "品赞代理签到",
    "dml_checkin": "达美乐任务",
    "xiaomao_checkin": "小茅预约（i茅台）",
    "ydwx_checkin": "一点万象签到",
    "xingkong_checkin": "星空代理签到",
    "qtw_checkin": "千图网签到",
    "freenom_checkin": "Freenom 免费域名续期",
    "weather_push": "天气每日推送",
    "kuake_checkin": "夸克网盘签到",
    "kjwj_checkin": "科技玩家签到",
    "fr_checkin": "帆软社区签到 + 摇摇乐",
    "nine_nine_nine_task": "999 会员中心健康打卡任务",
    "zgfc_draw": "中国福彩抽奖活动",
    "ssq_500w_notice": "双色球开奖通知（守号+冷号机选）",
    "demo_task": "示例任务（二次开发演示）",
}


def get_job_description(job_id: str) -> str:
    """根据任务 ID 获取任务描述。"""
    return JOB_DESCRIPTIONS.get(job_id, f"任务 {job_id}")
