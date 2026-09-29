"""B 阶段测试。

不依赖真实 ChatGPT 登录，验证：
1. Selector 集中定义（B2）：所有 selector 都来自 selectors.py；
2. ChatAdapter 抽象契约（B5）：ChatGPTAdapter 完整实现所有抽象方法；
3. ChatGPTAdapter 的逻辑（用 Fake Page 模拟 DOM 交互，B3/B4）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.adapters.base import ChatAdapter
from app.adapters.chatgpt.chat import ChatGPTAdapter
from app.adapters.chatgpt.selectors import ChatGPTSelectors, SELECTORS
from app.adapters.chatgpt.session import SessionConfig


# ---------------------------------------------------------------------------
# B2：selector 集中定义
# ---------------------------------------------------------------------------

def test_selectors_are_centralized():
    """所有 selector 都有 value 且集中在一个类里。"""
    s = ChatGPTSelectors()
    assert s.COMPOSER_TEXTAREA.value
    assert s.SEND_BUTTON.value
    assert s.FILE_INPUT.value
    assert s.RESPONSE_MARKDOWN.value
    assert s.STOP_GENERATING.value


def test_default_selectors_instance():
    assert SELECTORS.COMPOSER_TEXTAREA.value


# ---------------------------------------------------------------------------
# B5：抽象契约
# ---------------------------------------------------------------------------

def test_chatgpt_adapter_implements_full_interface():
    """ChatGPTAdapter 必须实现 ChatAdapter 的全部抽象方法。"""
    assert issubclass(ChatGPTAdapter, ChatAdapter)
    abstract = ChatAdapter.__abstractmethods__
    for name in abstract:
        assert hasattr(ChatGPTAdapter, name), f"缺少抽象方法实现：{name}"


def test_adapter_requires_attach_before_page():
    a = ChatGPTAdapter()
    with pytest.raises(RuntimeError):
        _ = a.page


def test_session_config_defaults():
    c = SessionConfig()
    assert c.base_url == "https://chatgpt.com/"
    assert c.headless is False


# ---------------------------------------------------------------------------
# B3/B4：逻辑测试（用 Fake Page，不连真实浏览器）
# ---------------------------------------------------------------------------

class _FakeEl:
    """模拟 Playwright 的单个元素（Locator）。"""

    def __init__(self, text="", attrs=None):
        self.text = text
        self.attrs = attrs or {}

    def inner_text(self):
        return self.text

    def get_attribute(self, name):
        return self.attrs.get(name)

    def click(self, timeout=None):
        return None

    def fill(self, text):
        return None

    def set_input_files(self, files):
        return None


class _FakeLocator:
    """模拟 Playwright 的 Locator（可匹配多个元素）。"""

    def __init__(self, elements=None):
        self._elements = elements or []  # list[_FakeEl]

    @property
    def first(self):
        return self._elements[0] if self._elements else _FakeEl()

    @property
    def last(self):
        return self._elements[-1] if self._elements else _FakeEl()

    def count(self):
        return len(self._elements)

    def all(self):
        return self._elements


class _FakePage:
    """记录 adapter 调用的假页面。"""

    def __init__(self):
        self.url = "https://chatgpt.com/"
        self.goto_calls = []
        self.uploaded = []
        self.sent = []
        self.submitted = False
        self._stop_count = 0
        self.response_blocks = [_FakeEl(text="你好，这是回复内容")]
        self.download_blocks = [_FakeEl(attrs={"href": "https://files/1.png"})]

    def goto(self, url):
        self.goto_calls.append(url)
        self.url = url

    def wait_for_load_state(self, state):
        return None

    def click(self, selector, timeout=None):
        return None

    def locator(self, selector):
        if "stop-button" in selector or "Stop" in selector:
            return _FakeLocator([_FakeEl()] * self._stop_count)
        if "type='file'" in selector:
            return _FakeLocator([_FakeEl()])
        if "textarea" in selector or "prompt" in selector:
            return _FakeLocator([_FakeEl()])
        if "send-button" in selector or "Send" in selector:
            return _FakeLocator([_FakeEl()])
        if "markdown" in selector or "assistant" in selector:
            return _FakeLocator(self.response_blocks)
        if "download" in selector or "blob:" in selector or "files" in selector:
            return _FakeLocator(self.download_blocks)
        return _FakeLocator([_FakeEl()])


@pytest.fixture
def fake_adapter():
    a = ChatGPTAdapter()
    a._page = _FakePage()
    return a


def test_send_text_and_submit(fake_adapter):
    fake_adapter.send_text("你好")
    fake_adapter.submit()
    # 无异常即通过（真实校验靠 get_response_text / wait 逻辑）


def test_get_response_text_returns_last_block(fake_adapter):
    assert fake_adapter.get_response_text() == "你好，这是回复内容"


def test_wait_until_complete_detects_done(fake_adapter):
    # 停止按钮数为 0 → 立即完成
    fake_adapter._page._stop_count = 0
    fake_adapter.wait_until_complete(timeout=5)


def test_wait_until_complete_times_out_when_still_generating(fake_adapter):
    fake_adapter._page._stop_count = 1  # 仍在生成
    fake_adapter.poll_interval = 0.01
    with pytest.raises(TimeoutError):
        fake_adapter.wait_until_complete(timeout=0.05)


def test_upload_files_sets_input(fake_adapter, tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    fake_adapter.upload_files([f])
    # 无异常即通过


def test_list_new_downloadables(fake_adapter):
    urls = fake_adapter.list_new_downloadables()
    assert urls == ["https://files/1.png"]
