"""Adapter 统一抽象（源自设计方案 §3.3）。

业务代码只依赖这里的抽象接口，不感知具体平台。
V1 优先级：ChatGPTAdapter > ChatGPTImageTaskAdapter > WorkHandoffAdapter > PPT Builder。
DeepSeek / 豆包留到 V2 扩展。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ChatAdapter(ABC):
    """Chat 类平台（ChatGPT 网页端）的统一接口。"""

    @abstractmethod
    def attach_session(self, *args: Any, **kwargs: Any) -> None: ...

    @abstractmethod
    def open_conversation(self, *args: Any, **kwargs: Any) -> str: ...

    @abstractmethod
    def new_conversation(self, *args: Any, **kwargs: Any) -> str: ...

    @abstractmethod
    def upload_files(self, files: list[Path]) -> None: ...

    @abstractmethod
    def send_text(self, text: str) -> None: ...

    @abstractmethod
    def submit(self) -> None: ...

    @abstractmethod
    def wait_until_complete(self, timeout: float | None = None) -> None: ...

    @abstractmethod
    def get_response_text(self) -> str: ...

    @abstractmethod
    def list_new_downloadables(self, boundary: Any) -> list[Any]: ...

    @abstractmethod
    def download(self, items: list[Any], output_dir: Path) -> list[Path]: ...

    @abstractmethod
    def recover_session(self, *args: Any, **kwargs: Any) -> None: ...
