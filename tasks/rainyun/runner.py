"""雨云签到运行器（参考 Rainyun-Qiandao main.run_with_config）"""

import logging
import os
import shutil

import ddddocr

from tasks.rainyun.api_client import RainyunAPI
from tasks.rainyun.browser.cookies import load_cookies
from tasks.rainyun.browser.pages import LoginPage, RewardPage
from tasks.rainyun.browser.session import BrowserSession, RuntimeContext
from tasks.rainyun.captcha import process_captcha
from tasks.rainyun.config_adapter import RainyunAccountConfig, RainyunRunConfig
from tasks.rainyun.server_manager import check_and_renew, generate_report

logger = logging.getLogger(__name__)


def _cookie_file_for_account(
    account: RainyunAccountConfig, base_dir: str = "data/rainyun_cookies"
) -> str:
    """为账号生成 cookie 文件路径"""
    os.makedirs(base_dir, exist_ok=True)
    identity = account.display_name or account.username
    if identity:
        import hashlib

        key = hashlib.sha256(identity.encode()).hexdigest()[:10]
    else:
        key = "default"
    return os.path.join(base_dir, f"cookies_{key}.json")


def _get_chrome_overrides() -> dict:
    """从环境变量获取 Chrome/Chromium 路径，Docker 部署时使用"""
    overrides = {}
    chrome_bin = os.environ.get("CHROME_BIN", "").strip()
    chromedriver = os.environ.get("CHROMEDRIVER_PATH", "").strip()
    if chrome_bin and os.path.exists(chrome_bin):
        overrides["chrome_bin"] = chrome_bin
    if chromedriver and os.path.exists(chromedriver):
        overrides["chromedriver_path"] = chromedriver
    return overrides


def run_single_account(account: RainyunAccountConfig, **config_overrides) -> tuple[bool, str]:
    """
    执行单个账号的签到流程（Selenium + 账号密码 + ddddocr）。
    返回 (成功, 推送内容)
    """
    cookie_file = account.cookie_file or _cookie_file_for_account(account)
    # 环境变量优先（Docker 部署时 CHROME_BIN、CHROMEDRIVER_PATH）
    merged = {**_get_chrome_overrides(), **config_overrides}
    config = RainyunRunConfig.from_account(
        account,
        cookie_file=cookie_file,
        **merged,
    )
    prefix = f"用户 {config.display_name} " if config.display_name else ""
    session = None
    temp_dir = None
    log_parts = []

    try:
        if not config.rainyun_user or not config.rainyun_pwd:
            logger.error("%s请配置账号用户名和密码", prefix)
            return False, "配置错误：缺少用户名或密码"

        api_client = RainyunAPI(config.rainyun_api_key, config) if config.rainyun_api_key else None
        start_points = 0
        if api_client:
            try:
                start_points = api_client.get_user_points()
                logger.info("%s签到前积分: %s", prefix, start_points)
            except Exception as e:
                logger.warning("%s获取积分失败: %s", prefix, e)

        logger.info("%s准备 OCR/DET", prefix)
        try:
            import cv2

            if not getattr(cv2, "imdecode", None):
                origin = getattr(cv2, "__file__", "未知")
                raise RuntimeError(
                    "当前环境中的 cv2 缺少 imdecode，验证码检测无法使用。"
                    f"当前 cv2 来自: {origin}。"
                    "若 opencv-python-headless 已安装仍报错，多为安装不完整，请在项目目录执行: uv pip install --force-reinstall opencv-python-headless；"
                    "若曾安装过占位包 cv2，请先执行 pip uninstall cv2。"
                )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                "无法加载 OpenCV (cv2)，验证码检测需要 opencv-python-headless。"
            ) from e

        ocr = ddddocr.DdddOcr(ocr=True, show_ad=False)
        det = ddddocr.DdddOcr(det=True, show_ad=False)

        linux = config.linux_mode
        if os.name != "nt" and "DISPLAY" not in os.environ:
            linux = True

        logger.info("%s初始化 Selenium", prefix)
        session = BrowserSession(config=config, debug=False, linux=linux)
        driver, wait, temp_dir = session.start()

        if api_client is None:
            api_client = RainyunAPI(config.rainyun_api_key or "dummy", config)

        ctx = RuntimeContext(
            driver=driver,
            wait=wait,
            ocr=ocr,
            det=det,
            temp_dir=temp_dir,
            api=api_client,
            config=config,
        )

        login_page = LoginPage(ctx, captcha_handler=process_captcha)
        reward_page = RewardPage(ctx, captcha_handler=process_captcha)

        logged_in = False
        if load_cookies(driver, config):
            logged_in = login_page.check_login_status()
        if not logged_in:
            logged_in = login_page.login(config.rainyun_user, config.rainyun_pwd)

        if not logged_in:
            logger.error("%s登录失败", prefix)
            return False, f"{prefix}登录失败，任务终止"

        reward_result = reward_page.handle_daily_reward(start_points)
        status = reward_result.get("status", "")
        if status == "already_signed":
            msg = f"{prefix}今日已签到，无需重复签到"
        else:
            earned = reward_result.get("earned")
            msg = (
                f"{prefix}签到成功！本次获得 {earned} 积分"
                if earned is not None
                else f"{prefix}签到成功"
            )

        log_parts.append(msg)
        logger.info("%s任务执行成功", prefix)

    except Exception as e:
        logger.error("%s脚本异常: %s", prefix, e, exc_info=True)
        log_parts.append(f"{prefix}签到失败: {e}")
        return False, "\n".join(log_parts)

    finally:
        if session:
            session.close()
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    server_report = ""
    if config.rainyun_api_key and (config.auto_renew or config.renew_product_ids):
        try:
            result = check_and_renew(config)
            server_report = generate_report(result, config)
        except Exception as e:
            logger.error("%s服务器检查失败: %s", prefix, e)
            server_report = f"\n\n⚠️ 服务器检查失败: {e}"

    full_msg = "\n".join(log_parts) + server_report
    return True, full_msg
