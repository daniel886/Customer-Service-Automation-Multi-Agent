"""WeChat Work (企业微信) integration.

Provides:

* GET  /integrations/wechat/callback   - URL verification (echo)
* POST /integrations/wechat/callback   - encrypted message reception

Outbound replies are sent via the active-message API.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import struct
import time
import xml.etree.ElementTree as ET
from typing import Optional

import httpx
from Crypto.Cipher import AES
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from core.chat_service import chat_service
from core.config import settings
from core.logger import logger


router = APIRouter()


# ---------------- Crypto helpers (WXBizMsgCrypt) ---------------- #


class _WXCrypto:
    def __init__(self, token: str, aes_key: str, corp_id: str) -> None:
        self.token = token
        self.corp_id = corp_id
        if aes_key:
            try:
                self.aes_key = base64.b64decode(aes_key + "=")
            except Exception:  # noqa: BLE001
                self.aes_key = b"\x00" * 32
        else:
            self.aes_key = b"\x00" * 32

    def _signature(self, *parts: str) -> str:
        items = sorted(parts)
        return hashlib.sha1("".join(items).encode()).hexdigest()

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        sig = self._signature(self.token, timestamp, nonce, echostr)
        if sig != msg_signature:
            raise HTTPException(401, "signature mismatch")
        return self._decrypt(echostr)

    def decrypt_message(
        self, msg_signature: str, timestamp: str, nonce: str, encrypt: str
    ) -> str:
        sig = self._signature(self.token, timestamp, nonce, encrypt)
        if sig != msg_signature:
            raise HTTPException(401, "signature mismatch")
        return self._decrypt(encrypt)

    def _decrypt(self, encrypted_b64: str) -> str:
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        plain = cipher.decrypt(base64.b64decode(encrypted_b64))
        pad = plain[-1]
        plain = plain[:-pad]
        # Strip 16 random bytes prefix + 4 bytes msg length + corpid suffix
        msg_len = struct.unpack(">I", plain[16:20])[0]
        return plain[20 : 20 + msg_len].decode("utf-8")


_crypto: Optional[_WXCrypto] = None


def _get_crypto() -> _WXCrypto:
    global _crypto
    if _crypto is None:
        _crypto = _WXCrypto(
            settings.wechat_work_token,
            settings.wechat_work_aes_key,
            settings.wechat_work_corp_id,
        )
    return _crypto


# ---------------- Access token cache ---------------- #


class _TokenCache:
    def __init__(self) -> None:
        self.token = ""
        self.expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get(self) -> str:
        async with self._lock:
            if self.token and time.time() < self.expires_at - 60:
                return self.token
            url = (
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
                f"?corpid={settings.wechat_work_corp_id}"
                f"&corpsecret={settings.wechat_work_secret}"
            )
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                data = resp.json()
            if data.get("errcode") not in (0, None):
                raise RuntimeError(f"wechat token error: {data}")
            self.token = data["access_token"]
            self.expires_at = time.time() + data.get("expires_in", 7200)
            return self.token


_token_cache = _TokenCache()


async def send_text_to_user(user_id: str, content: str) -> dict:
    """Push an active customer-service message to a WeChat Work user."""
    try:
        token = await _token_cache.get()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"WeChat token failed: {exc}")
        return {"ok": False, "error": str(exc)}
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    payload = {
        "touser": user_id,
        "msgtype": "text",
        "agentid": int(settings.wechat_work_agent_id or 0),
        "text": {"content": content},
        "safe": 0,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
    return resp.json()


# ---------------- Callback endpoints ---------------- #


@router.get("/wechat/callback")
async def wechat_verify(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """企业微信 URL 校验回调。"""
    try:
        plain = _get_crypto().verify_url(msg_signature, timestamp, nonce, echostr)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"wechat verify error: {exc}")
        raise HTTPException(400, "verify failed") from exc
    return PlainTextResponse(plain)


@router.post("/wechat/callback")
async def wechat_callback(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    body = await request.body()
    try:
        root = ET.fromstring(body)
        encrypt = root.findtext("Encrypt")
        if not encrypt:
            raise ValueError("missing Encrypt")
        plain_xml = _get_crypto().decrypt_message(msg_signature, timestamp, nonce, encrypt)
        msg = ET.fromstring(plain_xml)
        from_user = msg.findtext("FromUserName") or "anonymous"
        msg_type = msg.findtext("MsgType")
        content = msg.findtext("Content") or ""
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"wechat decrypt error: {exc}")
        return PlainTextResponse("ok")  # WeChat expects 200

    if msg_type != "text":
        return PlainTextResponse("ok")

    # Run agent workflow asynchronously and push reply via active-message API.
    async def _run() -> None:
        try:
            resp = await chat_service.handle_user_turn(
                message=content,
                channel="wechat",
                customer_id=from_user,
                customer_name=from_user,
                tenant_id=settings.default_tenant_id,
            )
            await send_text_to_user(from_user, resp["reply"])
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"wechat handle error: {exc}")

    asyncio.create_task(_run())
    return PlainTextResponse("ok")
