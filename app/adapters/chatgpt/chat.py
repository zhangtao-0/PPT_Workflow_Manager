"""ChatGPTAdapter（B3 + B4 + B5）。

实现 §3.3 的 ChatAdapter 抽象：上传、发送、等待回复完成、取回文本、
识别本轮新增下载资源。依赖 B1 的浏览器接管 + B2 的 selector 隔离。

所有 DOM 操作只通过 selectors.py 的集中定义，业务代码不直接写 selector。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from app.adapters.base import ChatAdapter
from app.adapters.chatgpt.selectors import SELECTORS
from app.adapters.chatgpt.session import ChatGPTBrowser, SessionConfig
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class ChatGPTAdapter(ChatAdapter):
    """ChatGPT 网页端适配器。"""

    def __init__(
        self,
        config: SessionConfig | None = None,
        selectors=None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        self.config = config or SessionConfig()
        self.sel = selectors or SELECTORS
        self.poll_interval = poll_interval
        self.timeout = timeout
        self._browser: ChatGPTBrowser | None = None
        self._page: Page | None = None

    # -- 生命周期 ---------------------------------------------------------
    def attach_session(self, config: SessionConfig | None = None) -> None:
        """接管已登录浏览器（程序不保存密码）。"""
        if config:
            self.config = config
        self._browser = ChatGPTBrowser(self.config)
        self._page = self._browser.start()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("尚未 attach_session")
        return self._page

    def close(self) -> None:
        if self._browser:
            self._browser.stop()
            self._browser = None
            self._page = None

    # -- 会话 -------------------------------------------------------------
    def open_conversation(self, url: str) -> str:
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        return self.page.url

    def new_conversation(self) -> str:
        self.page.goto("https://chatgpt.com/")
        try:
            self.page.click(self.sel.NEW_CHAT_BUTTON.value, timeout=5000)
        except Exception as e:  # pragma: no cover
            logger.warning("点击新建聊天失败：%s", e)
        self.page.wait_for_load_state("networkidle")
        return self.page.url

    def recover_session(self, url: str | None = None) -> str:
        """会话恢复：回到已知 URL 或当前页。"""
        if url:
            return self.open_conversation(url)
        return self.page.url

    # -- 输入 -------------------------------------------------------------
    def upload_files(self, files: list[Path]) -> None:
        file_input = self.page.locator(self.sel.FILE_INPUT.value).first
        file_input.set_input_files([str(f) for f in files])

    def send_text(self, text: str) -> None:
        box = self.page.locator(self.sel.COMPOSER_TEXTAREA.value).first
        box.click()
        box.fill(text)

    def submit(self) -> None:
        self.page.locator(self.sel.SEND_BUTTON.value).first.click()

    # -- 等待与取回 -------------------------------------------------------
    def wait_until_complete(self, timeout: float | None = None) -> None:
        """轮询直到停止生成按钮消失（即回复完成）。"""
        timeout = timeout or self.timeout
        deadline = time.time() + timeout
        stop_sel = self.sel.STOP_GENERATING.value
        while time.time() < deadline:
            try:
                if self.page.locator(stop_sel).count() == 0:
                    return
            except Exception:  # pragma: no cover
                pass
            time.sleep(self.poll_interval)
        raise TimeoutError(f"等待回复完成超时（{timeout}s）")

    def get_response_text(self) -> str:
        """取回最后一个 assistant 回复的文本。"""
        blocks = self.page.locator(self.sel.RESPONSE_MARKDOWN.value)
        if blocks.count() == 0:
            return ""
        return blocks.last.inner_text()

    # -- 下载资源边界 -----------------------------------------------------
    def list_new_downloadables(self, boundary: Any = None) -> list[str]:
        """返回当前页可见的下载/图片资源标识（URL）。

        V1 简化实现：返回所有匹配的资源 URL；task boundary 的增量 diff
        在 Phase C（图片 Task Boundary 与下载）用快照对比实现。
        """
        items: list[str] = []
        for el in self.page.locator(self.sel.DOWNLOAD_LINKS.value).all():
            url = el.get_attribute("href") or el.get_attribute("src")
            if url:
                items.append(url)
        return items

    def download(self, items: list[str], output_dir: Path) -> list[Path]:
        """下载指定 URL 到本地（占位：Phase C 完整实现）。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        return []


__all__ = ["ChatGPTAdapter"]
