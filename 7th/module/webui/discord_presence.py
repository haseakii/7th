import asyncio
import time

try:
    from pypresence import AioPresence
    HAS_PYPRESENCE = True
except ImportError:
    HAS_PYPRESENCE = False

    class AioPresence:
        """存根，pypresence 未安装时使用。"""
        def __init__(self, *args, **kwargs):
            pass

    def _noop(*args, **kwargs):
        pass


RPC = None


async def run():
    if not HAS_PYPRESENCE:
        return
    assert RPC is not None
    await RPC.connect()
    await RPC.update(state="E7 Shop Bot is running", start=time.time(), large_image="e7")


def init_discord_rpc():
    if not HAS_PYPRESENCE:
        return
    global RPC
    RPC = AioPresence("929437173764223057")
    asyncio.create_task(run())


def close_discord_rpc():
    if not HAS_PYPRESENCE or not RPC:
        return
    RPC.send_data(2, {'v': 1, 'client_id': RPC.client_id})
    RPC.sock_writer.close()
