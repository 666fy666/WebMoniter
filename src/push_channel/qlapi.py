"""
青龙面板 QLAPI 推送通道 - 使用青龙内置 systemNotify 发送通知

当脚本在青龙面板环境中运行时，使用 QLAPI.systemNotify 发送推送，
与青龙的「通知设置」保持一致，无需额外配置推送通道。

参考：https://qinglong.online/guide/user-guide/built-in-api
"""

from __future__ import annotations

from src.ql_compat import get_qlapi

from ._push_channel import PushChannel


class QLAPIPushChannel(PushChannel):
    """青龙 QLAPI 推送通道 - 调用 QLAPI.systemNotify"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self._qlapi = None

    def _get_qlapi(self):
        if self._qlapi is None:
            self._qlapi = get_qlapi()
        return self._qlapi

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """通过青龙 QLAPI.systemNotify 推送"""
        qlapi = self._get_qlapi()
        if qlapi is None:
            self.logger.warning("青龙 QLAPI 不可用，跳过推送（当前可能非青龙环境）")
            return {"status": "skipped", "reason": "QLAPI not available"}

        try:
            # QLAPI.systemNotify({ title: string, content: string, notificationInfo?: object })
            result = qlapi.systemNotify({"title": str(title), "content": str(content)})
            self.logger.debug("【推送_青龙QLAPI】成功")
            return {"status": "success", "raw": result}
        except Exception as e:
            self.logger.error("【推送_青龙QLAPI】失败: %s", e)
            raise
