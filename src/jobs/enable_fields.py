"""任务启用开关映射 - registry 与青龙 compat 共用单一真相源。"""

MONITOR_JOB_ENABLE_FIELD_MAP: dict[str, str] = {
    "weibo_monitor": "weibo_enable",
    "huya_monitor": "huya_enable",
    "bilibili_monitor": "bilibili_enable",
    "douyin_monitor": "douyin_enable",
    "douyu_monitor": "douyu_enable",
    "xhs_monitor": "xhs_enable",
}

TASK_JOB_ENABLE_FIELD_MAP: dict[str, str] = {
    "ikuuu_checkin": "checkin_enable",
    "tieba_checkin": "tieba_enable",
    "weibo_chaohua_checkin": "weibo_chaohua_enable",
    "rainyun_checkin": "rainyun_enable",
    "enshan_checkin": "enshan_enable",
    "tyyun_checkin": "tyyun_enable",
    "aliyun_checkin": "aliyun_enable",
    "smzdm_checkin": "smzdm_enable",
    "zdm_draw": "zdm_draw_enable",
    "fg_checkin": "fg_enable",
    "miui_checkin": "miui_enable",
    "iqiyi_checkin": "iqiyi_enable",
    "lenovo_checkin": "lenovo_enable",
    "lbly_checkin": "lbly_enable",
    "pinzan_checkin": "pinzan_enable",
    "dml_checkin": "dml_enable",
    "xiaomao_checkin": "xiaomao_enable",
    "ydwx_checkin": "ydwx_enable",
    "xingkong_checkin": "xingkong_enable",
    "freenom_checkin": "freenom_enable",
    "weather_push": "weather_enable",
    "qtw_checkin": "qtw_enable",
    "kuake_checkin": "kuake_enable",
    "kjwj_checkin": "kjwj_enable",
    "fr_checkin": "fr_enable",
    "nine_nine_nine_task": "nine_nine_nine_enable",
    "zgfc_draw": "zgfc_enable",
    "ssq_500w_notice": "ssq_500w_enable",
    "log_cleanup": "log_cleanup_enable",
    # demo_task 使用 plugins 配置，不在此列出
}
