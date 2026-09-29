"""B6 闭环验收（真实浏览器，标记 manual）。

验证一个普通图片/文档任务能从 Task → ChatGPT → 本地 Artifact 完整闭环
（对齐设计方案 §22 Phase B 验收）。

由于需要用户登录 ChatGPT + 以 CDP 端口启动浏览器，本测试默认 skip，
需要手动以如下方式运行：

1. 启动已登录的 Chrome/Edge，附加调试端口：
   chrome.exe --remote-debugging-port=9222 --user-data-dir=<你的 profile>
2. 设置环境变量 PWM_CDP_URL=http://127.0.0.1:9222
3. 运行：pytest tests/test_chatgpt_loop.py -s -m manual

注意：程序不保存 ChatGPT 密码（§18），登录由用户完成。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.adapters.chatgpt.chat import ChatGPTAdapter
from app.adapters.chatgpt.session import SessionConfig

pytestmark = [
    pytest.mark.manual,
    pytest.mark.skipif(
        os.environ.get("PWM_CDP_URL") is None,
        reason="需要已登录的 ChatGPT 浏览器（PWM_CDP_URL），见文件头说明",
    ),
]


@pytest.fixture
def adapter():
    cfg = SessionConfig(cdp_url=os.environ["PWM_CDP_URL"])
    a = ChatGPTAdapter(config=cfg)
    a.attach_session()
    yield a
    a.close()


def test_task_to_artifact_closed_loop(adapter, tmp_path):
    """发送一条简单文本，取回回复并写入本地 Artifact。"""
    adapter.new_conversation()
    adapter.send_text("回复我三个字：你好呀")
    adapter.submit()
    adapter.wait_until_complete(timeout=120)

    text = adapter.get_response_text()
    assert text, "回复文本不应为空"

    # 写入本地 artifact 文件
    out = tmp_path / "response.txt"
    out.write_text(text, encoding="utf-8")
    assert out.exists()
    assert len(text) > 0


def test_upload_and_download_boundary(adapter, tmp_path):
    """上传一个文件并检测下载资源边界（Phase C 会做完整 diff）。"""
    f = tmp_path / "input.txt"
    f.write_text("请描述这张图", encoding="utf-8")
    adapter.new_conversation()
    adapter.upload_files([f])
    adapter.send_text("收到后请回复：已收到")
    adapter.submit()
    adapter.wait_until_complete(timeout=120)
    urls = adapter.list_new_downloadables()
    # 至少能取回资源列表（可能为空，取决于对话内容）
    assert isinstance(urls, list)
