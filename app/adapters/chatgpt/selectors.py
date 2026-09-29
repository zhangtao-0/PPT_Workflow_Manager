"""Selector 隔离（B2，对齐设计方案 §10.2）。

ChatGPT 网页 DOM 频繁变化，所有 selector 必须集中在本文件，业务代码
禁止直接引用网页 selector。若 DOM 变更，只改这里，不改业务代码。

字段含义：
- value : 当前使用的 selector
- since : 该 selector 生效的 DOM 版本标记（用于追踪变更历史）
- note  : 用途说明

注意：ChatGPT 网页结构会随官方更新而变化，以下 selector 是 V1 基线，
实际登录后若定位失败，需在此处校准并 bump `since`。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Selector:
    value: str
    since: str = "v1"
    note: str = ""


class ChatGPTSelectors:
    """ChatGPT 网页端 selector 集中定义。"""

    # 会话入口
    NEW_CHAT_BUTTON = Selector(
        value="a[href='/']", since="v1", note="左侧『新建聊天』入口"
    )

    # 输入区
    COMPOSER_TEXTAREA = Selector(
        value="div#prompt-textarea, textarea[data-testid='prompt-textarea']",
        since="v1",
        note="输入框，兼容 id 与 data-testid 两种定位",
    )
    SEND_BUTTON = Selector(
        value="button[data-testid='send-button'], button[aria-label*='Send']",
        since="v1",
        note="发送按钮",
    )
    FILE_INPUT = Selector(
        value="input[type='file']",
        since="v1",
        note="上传文件的原生 input（隐藏，需 set_input_files）",
    )

    # 回复区
    RESPONSE_MARKDOWN = Selector(
        value="div.markdown, div[data-message-author-role='assistant']",
        since="v1",
        note="assistant 回复内容容器",
    )
    STOP_GENERATING = Selector(
        value="button[data-testid='stop-button'], button[aria-label*='Stop']",
        since="v1",
        note="停止生成按钮，用于判断是否仍在生成中",
    )

    # 下载资源
    DOWNLOAD_LINKS = Selector(
        value="a[download], a[href*='blob:'], img[src^='https://files']",
        since="v1",
        note="可下载附件 / 图片",
    )


# 默认实例
SELECTORS = ChatGPTSelectors()


__all__ = ["Selector", "ChatGPTSelectors", "SELECTORS"]
