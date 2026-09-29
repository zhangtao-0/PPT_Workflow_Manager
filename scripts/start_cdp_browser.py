"""启动带 CDP 调试端口的 Chrome（独立 profile，不干扰日常浏览器）。

用途：Phase B/C 的真实闭环测试需要用户登录 ChatGPT 的浏览器实例。

用法：
    python scripts/start_cdp_browser.py [--port 9222] [--profile <目录>]

启动后：
1. 会弹出一个全新的 Chrome 窗口（独立 profile，未登录）；
2. 在这个窗口里登录 chatgpt.com；
3. 保持该窗口打开，然后设 PWM_CDP_URL 跑真实闭环测试。

说明：
- 用独立 profile 是为了避免与日常 Chrome 冲突，也让 --remote-debugging-port 真正生效。
- Chrome 以脱离当前进程的方式启动，关闭终端不影响它。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# 常见浏览器路径（按优先级）
BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> str | None:
    for p in BROWSER_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def wait_port_ready(port: int, timeout: float = 15.0) -> bool:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="启动带 CDP 端口的 Chrome")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--profile", type=str, default=r"C:\Users\tk457\Desktop\pwm_chrome_profile")
    args = ap.parse_args(argv)

    browser = find_browser()
    if browser is None:
        print("未找到 Chrome/Edge，请手动指定浏览器路径", file=sys.stderr)
        return 1

    cmd = [
        browser,
        f"--remote-debugging-port={args.port}",
        f"--user-data-dir={args.profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        "https://chatgpt.com/",
    ]

    # DETACHED_PROCESS：让 Chrome 脱离本进程，关闭终端不影响它
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    )

    print(f"浏览器已启动：{browser}")
    print(f"调试端口：{args.port}，profile：{args.profile}")
    print("等待 DevTools 就绪...")
    if wait_port_ready(args.port):
        print(f"\n✓ DevTools 已就绪：http://127.0.0.1:{args.port}")
        print("\n接下来：")
        print("1. 在弹出的 Chrome 窗口里登录 chatgpt.com")
        print("2. 登录后保持窗口打开")
        print(f"3. 设置环境变量后跑闭环测试：")
        print(f'   export PWM_CDP_URL=http://127.0.0.1:{args.port}')
        print("   pytest tests/test_chatgpt_loop.py -m manual")
        return 0
    print("\n✗ DevTools 未就绪，请检查是否有其他 Chrome 占用端口", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
