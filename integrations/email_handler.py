"""Email integration: SMTP send + IMAP poller for incoming customer mails."""
from __future__ import annotations

import asyncio
import email
import imaplib
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Optional

from core.chat_service import chat_service
from core.config import settings
from core.logger import logger


async def send_email(
    to: str,
    subject: str,
    body: str,
    from_addr: Optional[str] = None,
) -> bool:
    if not settings.email_enabled:
        logger.info(f"[email] disabled, would send to {to}: {subject}")
        return False

    msg = EmailMessage()
    msg["From"] = from_addr or settings.email_username
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    def _send_sync() -> None:
        if settings.smtp_tls and settings.smtp_port == 465:
            srv = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
        else:
            srv = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            if settings.smtp_tls:
                srv.starttls()
        try:
            srv.login(settings.email_username, settings.email_password)
            srv.send_message(msg)
        finally:
            srv.quit()

    try:
        await asyncio.to_thread(_send_sync)
        logger.info(f"[email] sent to {to}: {subject}")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[email] send failed: {exc}")
        return False


def _fetch_unread() -> list[tuple[str, str, str]]:
    """Synchronously fetch unread mails. Returns [(from, subject, body), ...]."""
    out: list[tuple[str, str, str]] = []
    try:
        m = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
        m.login(settings.email_username, settings.email_password)
        m.select("INBOX")
        typ, data = m.search(None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            m.logout()
            return out
        for num in data[0].split():
            typ, msg_data = m.fetch(num, "(RFC822)")
            if typ != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            sender = parseaddr(msg.get("From", ""))[1]
            subject = msg.get("Subject", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="ignore"
                        )
                        break
            else:
                body = msg.get_payload(decode=True).decode(
                    msg.get_content_charset() or "utf-8", errors="ignore"
                )
            out.append((sender, subject, body))
            try:
                m.store(num, "+FLAGS", "\\Seen")
            except Exception:  # noqa: BLE001
                pass
        m.logout()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[email] poll failed: {exc}")
    return out


async def poll_inbox_loop() -> None:
    """Background task: poll inbox at the configured interval."""
    if not settings.email_enabled:
        logger.info("[email] disabled, poller not started")
        return
    logger.info(
        f"[email] poller started, interval={settings.email_poll_interval_seconds}s"
    )
    while True:
        try:
            mails = await asyncio.to_thread(_fetch_unread)
            for sender, subject, body in mails:
                msg = f"主题: {subject}\n\n{body}"
                resp = await chat_service.handle_user_turn(
                    message=msg,
                    channel="email",
                    customer_id=sender,
                    customer_name=sender,
                )
                await send_email(
                    to=sender,
                    subject=f"Re: {subject}",
                    body=resp["reply"],
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[email] loop error: {exc}")
        await asyncio.sleep(settings.email_poll_interval_seconds)
