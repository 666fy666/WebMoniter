from . import PushChannel


class Demo(PushChannel):
    """Demo 推送通道（用于测试）"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        # 在这里初始化通道需要的参数
        self.param = str(config.get("param", ""))
        if self.param == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息（Demo，仅记录日志）"""
        # 在这里实现推送逻辑，记得要在 push_channel/__init__.py 中注册推送通道
        self.logger.info(f"【推送_{self.name}】Demo推送: {title} - {content}")
        return {"status": "success"}
