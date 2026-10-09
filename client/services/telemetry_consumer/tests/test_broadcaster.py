from telemetry_consumer.broadcaster import Broadcaster


class FakeWS:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def send_json(self, message):
        if self.fail:
            raise RuntimeError("closed")
        self.sent.append(message)


async def test_broadcast_reaches_registered():
    broadcaster = Broadcaster()
    ws = FakeWS()
    await broadcaster.register(ws)
    await broadcaster.broadcast({"ok": True})
    assert ws.sent == [{"ok": True}]
    await broadcaster.unregister(ws)
    assert broadcaster.count == 0


async def test_broadcast_ignores_failed_send():
    broadcaster = Broadcaster()
    bad = FakeWS()
    bad.fail = True
    await broadcaster.register(bad)
    await broadcaster.broadcast({"ok": True})
    assert broadcaster.count == 0
