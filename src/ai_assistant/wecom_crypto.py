"""企业微信消息加解密 - 使用官方 WXBizMsgCrypt 库

官方库：src/weworkapi_python/callback_python3/WXBizMsgCrypt.py
文档：https://developer.work.weixin.qq.com/document/path/90968
"""

import logging
import sys
from pathlib import Path

from urllib.parse import unquote

logger = logging.getLogger(__name__)

# 加载官方 WXBizMsgCrypt（callback_python3 为 XML 格式，适配接收消息）
_callback_dir = Path(__file__).resolve().parent.parent / "weworkapi_python" / "callback_python3"
if _callback_dir.exists() and str(_callback_dir) not in sys.path:
    sys.path.insert(0, str(_callback_dir))

# cElementTree 已在 Python 3.3+ 弃用，兼容：将 cElementTree 映射到 ElementTree
import xml.etree.ElementTree as _ET
if "xml.etree.cElementTree" not in sys.modules:
    sys.modules["xml.etree.cElementTree"] = _ET

try:
    from WXBizMsgCrypt import WXBizMsgCrypt
    from ierror import (
        WXBizMsgCrypt_OK,
        WXBizMsgCrypt_DecryptAES_Error,
        WXBizMsgCrypt_ValidateCorpid_Error,
        WXBizMsgCrypt_ValidateSignature_Error,
        WXBizMsgCrypt_ParseXml_Error,
    )
    _OFFICIAL_AVAILABLE = True
except ImportError as e:
    logger.warning("企业微信官方 WXBizMsgCrypt 加载失败，使用内置实现: %s", e)
    _OFFICIAL_AVAILABLE = False


def decrypt_msg(
    token: str,
    encoding_aes_key: str,
    corp_id: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    post_data: str,
) -> str:
    """
    解密企业微信回调消息。优先使用官方 WXBizMsgCrypt 库。
    """
    if _OFFICIAL_AVAILABLE:
        try:
            wxcpt = WXBizMsgCrypt(token, encoding_aes_key, corp_id)
            ret, xml_content = wxcpt.DecryptMsg(
                post_data, msg_signature, timestamp, nonce
            )
            if ret == WXBizMsgCrypt_OK:
                return xml_content.decode("utf-8") if isinstance(xml_content, bytes) else xml_content
            if ret == WXBizMsgCrypt_ValidateSignature_Error:
                raise ValueError("签名校验失败")
            if ret == WXBizMsgCrypt_ValidateCorpid_Error:
                raise ValueError(f"ReceiveId 不匹配: 期望 {corp_id}")
            if ret == WXBizMsgCrypt_ParseXml_Error:
                raise ValueError("无法从 POST 数据中解析 Encrypt 节点")
            if ret == WXBizMsgCrypt_DecryptAES_Error:
                raise ValueError(
                    "AES 解密失败: 请确认 config 中 encoding_aes_key、corp_id、callback_token "
                    "与企微后台「接收消息」里该应用的配置完全一致，且 EncodingAESKey 为 43 字符无多余空格"
                )
            raise ValueError(f"解密失败，错误码: {ret}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"解密失败: {e}") from e

    # 回退到内置实现
    return _decrypt_msg_fallback(
        token, encoding_aes_key, corp_id,
        msg_signature, timestamp, nonce, post_data
    )


def _decrypt_msg_fallback(
    token: str,
    encoding_aes_key: str,
    corp_id: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    post_data: str,
) -> str:
    """内置解密实现（官方库不可用时的回退）"""
    import base64
    import re
    import struct
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    def _extract_encrypt(xml_text: str) -> str | None:
        m = re.search(r"<Encrypt><!\[CDATA\[(.*?)\]\]></Encrypt>", xml_text, re.DOTALL)
        if m:
            return m.group(1)
        m = re.search(r"<Encrypt>(.*?)</Encrypt>", xml_text, re.DOTALL)
        return m.group(1).strip() if m else None

    def _verify_sig(t: str, ts: str, n: str, e: str, sig: str) -> bool:
        import hashlib
        arr = sorted([t, ts, n, e])
        return hashlib.sha1("".join(arr).encode()).hexdigest() == sig

    encrypt_raw = _extract_encrypt(post_data)
    if not encrypt_raw:
        raise ValueError("无法从 POST 数据中解析 Encrypt 节点")
    if not _verify_sig(token, timestamp, nonce, encrypt_raw, msg_signature):
        raise ValueError("签名校验失败")

    key = (encoding_aes_key or "").strip()
    if len(key) == 43:
        key += "="
    elif len(key) != 44:
        raise ValueError("EncodingAESKey 须为 43 或 44 字符")
    aes_key = base64.b64decode(key)
    iv = aes_key[:16]

    for enc in [encrypt_raw.strip(), unquote(encrypt_raw.strip()).replace(" ", "+")]:
        try:
            pad_len = 4 - (len(enc) % 4)
            if pad_len and pad_len != 4:
                enc = enc + ("=" * pad_len)
            aes_msg = base64.b64decode(enc)
        except Exception:
            continue
        if len(aes_msg) % AES.block_size != 0:
            continue
        try:
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            rand_msg = unpad(cipher.decrypt(aes_msg), AES.block_size)
        except Exception:
            continue
        msg_len = struct.unpack(">I", rand_msg[16:20])[0]
        msg = rand_msg[20 : 20 + msg_len].decode("utf-8")
        receive_id = rand_msg[20 + msg_len :].decode("utf-8")
        if receive_id != corp_id:
            raise ValueError(f"ReceiveId 不匹配: 期望 {corp_id}, 得到 {receive_id}")
        return msg

    raise ValueError(
        "AES 解密失败: 请确认 config 中 encoding_aes_key、corp_id、callback_token "
        "与企微后台「接收消息」里该应用的配置完全一致"
    )


def encrypt_msg(
    token: str,
    encoding_aes_key: str,
    reply_msg: str,
    timestamp: str,
    nonce: str,
    corp_id: str,
) -> str:
    """
    加密被动回复消息。优先使用官方 WXBizMsgCrypt 库。
    """
    if _OFFICIAL_AVAILABLE:
        try:
            wxcpt = WXBizMsgCrypt(token, encoding_aes_key, corp_id)
            ret, encrypted_xml = wxcpt.EncryptMsg(reply_msg, nonce, timestamp)
            if ret == WXBizMsgCrypt_OK:
                return encrypted_xml
            raise ValueError(f"加密失败，错误码: {ret}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"加密失败: {e}") from e

    return _encrypt_msg_fallback(
        token, encoding_aes_key, reply_msg, timestamp, nonce, corp_id
    )


def _encrypt_msg_fallback(
    token: str,
    encoding_aes_key: str,
    reply_msg: str,
    timestamp: str,
    nonce: str,
    corp_id: str,
) -> str:
    """内置加密实现"""
    import base64
    import hashlib
    import random
    import string
    import struct
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    key = (encoding_aes_key or "").strip()
    if len(key) == 43:
        key += "="
    aes_key = base64.b64decode(key)
    iv = aes_key[:16]

    msg_bytes = reply_msg.encode("utf-8")
    rand_str = "".join(random.choices(string.ascii_letters + string.digits, k=16)).encode()
    plain = rand_str + struct.pack(">I", len(msg_bytes)) + msg_bytes + corp_id.encode("utf-8")
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    encrypted = base64.b64encode(cipher.encrypt(pad(plain, AES.block_size))).decode()

    arr = sorted([token, timestamp, nonce, encrypted])
    signature = hashlib.sha1("".join(arr).encode()).hexdigest()
    return f"""<xml>
<Encrypt><![CDATA[{encrypted}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
