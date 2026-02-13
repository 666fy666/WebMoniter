"""企业微信消息加解密 - 参考官方文档 https://developer.work.weixin.qq.com/document/path/90968"""

import base64
import hashlib
import random
import re
import struct
import string

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# XML 解析使用正则，避免依赖 lxml
def _extract_cdata(tag: str, xml: str) -> str | None:
    m = re.search(rf"<{tag}><!\[CDATA\[(.*?)\]\]></{tag}>", xml, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return m.group(1) if m else None


def _get_aes_key(encoding_aes_key: str) -> bytes:
    """EncodingAESKey 为 43 字符，Base64 解码后补 = 得 32 字节 AESKey"""
    key = encoding_aes_key
    if len(key) == 43:
        key += "="
    return base64.b64decode(key)


def _get_iv(aes_key: bytes) -> bytes:
    """IV 取 AESKey 前 16 字节"""
    return aes_key[:16]


def verify_signature(token: str, timestamp: str, nonce: str, msg_encrypt: str, signature: str) -> bool:
    """验证消息签名"""
    arr = sorted([token, timestamp, nonce, msg_encrypt])
    concat = "".join(arr)
    digest = hashlib.sha1(concat.encode()).hexdigest()
    return digest == signature


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
    解密企业微信回调消息。

    Args:
        token: 应用回调配置的 Token
        encoding_aes_key: 应用回调配置的 EncodingAESKey（43 字符）
        corp_id: 企业 ID，作为 ReceiveId
        msg_signature: URL 参数 msg_signature
        timestamp: URL 参数 timestamp
        nonce: URL 参数 nonce
        post_data: POST 请求体 XML 字符串

    Returns:
        解密后的明文 XML 消息

    Raises:
        ValueError: 签名校验失败或解密失败
    """
    encrypt = _extract_cdata("Encrypt", post_data) or _extract_cdata("encrypt", post_data)
    if not encrypt:
        raise ValueError("无法从 POST 数据中解析 Encrypt 节点")

    if not verify_signature(token, timestamp, nonce, encrypt, msg_signature):
        raise ValueError("签名校验失败")

    aes_key = _get_aes_key(encoding_aes_key)
    iv = _get_iv(aes_key)

    try:
        aes_msg = base64.b64decode(encrypt)
    except Exception as e:
        raise ValueError(f"Base64 解码失败: {e}") from e

    try:
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        rand_msg = unpad(cipher.decrypt(aes_msg), AES.block_size)
    except Exception as e:
        raise ValueError(f"AES 解密失败: {e}") from e

    # rand_msg: 16 字节随机 + 4 字节 msg_len(大端) + msg + receiveid
    msg_len = struct.unpack(">I", rand_msg[16:20])[0]
    msg = rand_msg[20 : 20 + msg_len].decode("utf-8")
    receive_id = rand_msg[20 + msg_len :].decode("utf-8")

    if receive_id != corp_id:
        raise ValueError(f"ReceiveId 不匹配: 期望 {corp_id}, 得到 {receive_id}")

    return msg


def encrypt_msg(
    token: str,
    encoding_aes_key: str,
    reply_msg: str,
    timestamp: str,
    nonce: str,
    corp_id: str,
) -> str:
    """
    加密被动回复消息。

    Args:
        token: 应用回调配置的 Token
        encoding_aes_key: 应用回调配置的 EncodingAESKey
        reply_msg: 明文回复 XML
        timestamp: 时间戳字符串
        nonce: 随机数
        corp_id: 企业 ID 作为 ReceiveId

    Returns:
        加密后的 XML 响应包
    """
    aes_key = _get_aes_key(encoding_aes_key)
    iv = _get_iv(aes_key)

    msg_bytes = reply_msg.encode("utf-8")
    msg_len = len(msg_bytes)
    receive_id_bytes = corp_id.encode("utf-8")

    rand_str = "".join(random.choices(string.ascii_letters + string.digits, k=16)).encode()
    len_bytes = struct.pack(">I", msg_len)
    plain = rand_str + len_bytes + msg_bytes + receive_id_bytes

    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    padded = pad(plain, AES.block_size)
    encrypted = cipher.encrypt(padded)
    msg_encrypt = base64.b64encode(encrypted).decode()

    # 签名
    arr = sorted([token, timestamp, nonce, msg_encrypt])
    concat = "".join(arr)
    signature = hashlib.sha1(concat.encode()).hexdigest()

    return f"""<xml>
<Encrypt><![CDATA[{msg_encrypt}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
