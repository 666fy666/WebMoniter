from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from . import PushChannel


class Email(PushChannel):
    """邮件推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.smtp_host = str(config.get("smtp_host", ""))
        self.smtp_port = int(config.get("smtp_port", 465))
        self.smtp_ssl = config.get("smtp_ssl", True)
        self.smtp_tls = config.get("smtp_tls", False)
        self.sender_email = str(config.get("sender_email", ""))
        self.sender_password = str(config.get("sender_password", ""))
        self.receiver_email = str(config.get("receiver_email", ""))
        if (
            self.smtp_host == ""
            or self.smtp_port == 0
            or self.sender_email == ""
            or self.sender_password == ""
            or self.receiver_email == ""
        ):
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        message = MIMEMultipart()
        message["Subject"] = title
        message["From"] = self.sender_email
        message["To"] = self.receiver_email

        body = f"{content}"
        if jump_url:
            body += f'<br><a href="{jump_url}">点击查看详情</a>'
        if pic_url is not None:
            body += f'<br><img src="{pic_url}">'
        message.attach(MIMEText(body, "html", "utf-8"))

        try:
            # 对于 465 端口（SSL），使用 SMTP_SSL；对于 587 端口（TLS），使用 SMTP + start_tls
            if self.smtp_port == 465:
                # SSL 连接（465端口）
                smtp_client = aiosmtplib.SMTP(
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    use_tls=True,  # SSL 连接
                )
            else:
                # TLS 连接（587端口或其他）
                smtp_client = aiosmtplib.SMTP(
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    use_tls=False,
                )

            await smtp_client.connect()

            # 如果需要 TLS（587端口），启动 TLS
            if self.smtp_tls and self.smtp_port != 465:
                await smtp_client.starttls()

            # 登录
            await smtp_client.login(self.sender_email, self.sender_password)

            # 发送邮件
            await smtp_client.send_message(message)

            # 关闭连接
            await smtp_client.quit()

            self.logger.info(f"【推送_{self.name}】成功")
            return {"status": "success"}
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}", exc_info=True)
            raise
