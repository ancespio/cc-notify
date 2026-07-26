"""Feishu WebSocket event service backed by the official Python SDK."""

import asyncio
import json
import threading
from typing import Any, Callable


class FeishuWebSocketService:
    """Receive Feishu message events without polling message history."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
    ):
        self.app_id = str(app_id or "").strip()
        self.app_secret = str(app_secret or "").strip()
        self._ws_client: Any = None
        self._ws_module: Any = None
        self._api_client: Any = None
        self._stop_requested = False

    def _load_sdk(self) -> Any:
        if not self.app_id or not self.app_secret:
            raise ValueError("飞书 WebSocket 需要配置 app_id 和 app_secret。")
        try:
            import lark_oapi as lark
            import lark_oapi.ws.client as ws_module
        except ImportError as exc:
            raise RuntimeError(
                "未安装 lark-oapi，请先安装 requirements.txt 中的依赖。"
            ) from exc
        self._ws_module = ws_module
        return lark

    @staticmethod
    def normalize_message(data: Any) -> dict[str, Any] | None:
        """Convert an SDK event object to the controller's stable shape."""
        event = getattr(data, "event", None)
        message = getattr(event, "message", None)
        if message is None:
            return None
        sender = getattr(event, "sender", None)
        sender_id = getattr(sender, "sender_id", None)
        open_id = str(getattr(sender_id, "open_id", "") or "")
        return {
            "message_id": str(getattr(message, "message_id", "") or ""),
            "chat_id": str(getattr(message, "chat_id", "") or ""),
            "sender": {"id": open_id},
            "body": {
                "content": str(getattr(message, "content", "") or ""),
            },
        }

    def run(
        self,
        on_message: Callable[[dict[str, Any]], None],
        stop_event: threading.Event,
    ) -> None:
        """Block while the SDK receives events and stop on ``stop_event``."""
        lark = self._load_sdk()
        self._stop_requested = False

        def handle_message(data: Any) -> None:
            message = self.normalize_message(data)
            if message is not None:
                on_message(message)

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(handle_message)
            .build()
        )
        self._ws_client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            auto_reconnect=True,
        )

        watcher = threading.Thread(
            target=self._wait_for_stop,
            args=(stop_event,),
            daemon=True,
        )
        watcher.start()
        if stop_event.is_set():
            self.stop()
            return

        try:
            self._ws_client.start()
        except RuntimeError:
            if not self._stop_requested:
                raise
        finally:
            self._ws_client = None
            self._ws_module = None

    def _wait_for_stop(self, stop_event: threading.Event) -> None:
        if stop_event.wait():
            self.stop()

    def stop(self) -> None:
        """Close the SDK connection without waiting on the event callback."""
        self._stop_requested = True
        client = self._ws_client
        module = self._ws_module
        loop = getattr(module, "loop", None)
        if client is None or loop is None:
            return
        client._auto_reconnect = False

        async def close_connection() -> None:
            await client._disconnect()
            loop.stop()

        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(close_connection(), loop=loop)
        )

    def reply(self, message_id: str, text: str) -> None:
        """Reply to a received message through Feishu OpenAPI."""
        lark = self._load_sdk()
        from lark_oapi.api.im.v1 import (
            ReplyMessageRequest,
            ReplyMessageRequestBody,
        )

        if self._api_client is None:
            self._api_client = (
                lark.Client.builder()
                .app_id(self.app_id)
                .app_secret(self.app_secret)
                .build()
            )
        client = self._api_client
        request = ReplyMessageRequest.builder().message_id(
            message_id
        ).request_body(
            ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(
                json.dumps({"text": text}, ensure_ascii=False)
            )
            .build()
        ).build()
        response = client.im.v1.message.reply(request)
        if not response.success():
            raise OSError(
                f"飞书回复失败：{response.code} {response.msg}"
            )
