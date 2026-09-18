"""启动入口：python run.py

默认只监听 127.0.0.1，也就是只有本机能访问。
要让手机 / 平板 / 别的电脑连进来，把监听地址放开：

    HOST=0.0.0.0 python run.py      # 临时
    # 或在 .env 里写 HOST=0.0.0.0   # 持久（推荐）

注意：一旦监听 0.0.0.0，同网段任何人都能调用接口、消耗你的 DeepSeek 额度，
所以请同时在 .env 里设置 API_TOKEN。详见 README「路演接入：手机 / 隧道」。
"""
import socket

import uvicorn

from app.config import settings


def lan_ip() -> str:
    """取本机在局域网里的出口 IP，用于提示手机该访问哪个地址。

    连一个 UDP 地址不会真的发包，只是让系统挑一张出口网卡；失败时退回 127.0.0.1。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def print_banner() -> None:
    line = "=" * 62
    print(line)
    print(f"  X University AI Backend   model={settings.model}   mock={settings.mock_mode}")
    print("-" * 62)
    print(f"  本机访问    http://127.0.0.1:{settings.port}/docs")
    if settings.exposed_to_network:
        print(f"  局域网访问  http://{lan_ip()}:{settings.port}/docs   <- 手机浏览器用这个")
    else:
        print("  局域网访问  未开启（HOST=127.0.0.1，仅本机可访问）")
    print(f"  接口鉴权    {'已启用（/api/* 需带 X-API-Token）' if settings.api_token else '未启用'}")
    print(f"  热重载      {'开' if settings.reload else '关'}")
    print(line)
    if settings.exposed_to_network and not settings.api_token:
        print("  !! 已监听 0.0.0.0 但 API_TOKEN 为空：同网段任何人都能调用接口并消耗额度。")
        print("     请执行：python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        print("     把结果写进 .env 的 API_TOKEN，然后重启。")
        print(line)


if __name__ == "__main__":
    print_banner()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.reload)
