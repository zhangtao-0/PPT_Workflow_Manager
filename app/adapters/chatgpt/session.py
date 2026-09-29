"""浏览器接管与会话管理（B1，对齐设计方案 §10.1/§10.3）。

策略：
- 用户自己登录 ChatGPT（网页端），程序不保存密码。
- 通过 CDP 接管已启动的 Chrome/Edge（用户以 --remote-debugging-port 启动），
  或启动持久化 Context 复用已有 Profile。
- 会话管理支持 continue / isolated / batch 三种模式（§10.3）。

安全（§18）：CDP 仅绑定本机；浏览器 Profile 与项目数据分离；不保存凭据。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """会话/浏览器配置。"""

    cdp_url: str | None = None           # 例 http://127.0.0.1:9222
    user_data_dir: str | None = None     # 持久化 Profile 目录（与项目数据分离）
    base_url: str = "https://chatgpt.com/"
    headless: bool = False


class ChatGPTBrowser:
    """Playwright 同步 API 的浏览器接管封装。"""

    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def start(self) -> Page:
        """启动并返回一个可用页面。

        优先级：CDP 接管 > 持久化 Profile 启动。二者都未配置时抛错。
        """
        self._pw = sync_playwright().start()
        if self.config.cdp_url:
            self._browser = self._pw.chromium.connect_over_cdp(self.config.cdp_url)
            self._context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        elif self.config.user_data_dir:
            self._context = self._pw.chromium.launch_persistent_context(
                user_data_dir=self.config.user_data_dir,
                headless=self.config.headless,
                args=["--remote-debugging-port=9222"],
            )
            self._browser = None
        else:
            raise RuntimeError("需配置 cdp_url 或 user_data_dir（用户自行登录，程序不存密码）")

        page = self._context.pages[0] if self._context.pages else self._context.new_page()
        if not page.url.startswith("http"):
            page.goto(self.config.base_url)
        return page

    def stop(self) -> None:
        if self._context is not None:
            # 持久化 context 关闭会保存 Profile；CDP 接管不关闭远端浏览器
            if self.config.cdp_url is None:
                self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()
        self._context = None
        self._browser = None
        self._pw = None


class ConversationManager:
    """会话策略管理（§10.3）：continue / isolated / batch。"""

    def __init__(self, page: Page, selectors: Any) -> None:
        self.page = page
        self.sel = selectors

    def new_conversation(self) -> str:
        """新建对话，返回该对话标识（V1 用当前 URL 作为标识）。"""
        self.page.goto("https://chatgpt.com/")
        # 点击新建入口
        try:
            self.page.click(self.sel.NEW_CHAT_BUTTON.value, timeout=5000)
        except Exception as e:  # pragma: no cover - 依赖真实 DOM
            logger.warning("点击新建聊天失败：%s", e)
        self.page.wait_for_load_state("networkidle")
        return self.page.url

    def current_id(self) -> str:
        return self.page.url

    def open_conversation(self, url: str) -> str:
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        return self.page.url


__all__ = ["ChatGPTBrowser", "ConversationManager", "SessionConfig"]
