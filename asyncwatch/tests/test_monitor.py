import os
from pathlib import Path

import pytest
import curio

from asyncwatch import Monitor, watch, EVENTS


async def touch(p):
    new_path = p/'xxx'
    async with curio.aopen(str(new_path), 'a') as f:
        pass
    return new_path


def test_iter(tmpdir):
    p = Path(str(tmpdir))
    async def do_watch():
        count = 0
        async for events in  watch(str(p), EVENTS.IN_CREATE):
            count += 1
            (p / str(count)).touch()
            if count == 5:
                break
        assert count == 5


    async def main():
        t = await curio.spawn(do_watch())
        await touch(p)
        await t.join()
    curio.run(main())


def test_context(tmpdir):
    async def do_watch():
        monitor = watch(str(tmpdir), EVENTS.IN_DELETE, oneshot=True)
        async with monitor as events:
            assert any(event.tp ==  EVENTS.IN_DELETE for event in
                    events)
        with pytest.raises(OSError):
            os.fstat(monitor._fd)

    async def main():
        t = await curio.spawn(do_watch())
        np = await touch(tmpdir)
        #Ugly!
        Path(str(np)).unlink()
        await t.join()

    curio.run(main())


def test_bad():
    m = Monitor()
    with pytest.raises(OSError):
        m.add_watch('/', 123212313)

def test_several(tmpdir):
    m = Monitor()
    m.add_watch(str(tmpdir), (EVENTS.IN_ACCESS, EVENTS.IN_CREATE))
    async def main():
        tmpdir.mkdir('xxx')
        events = await m.next_events()
        assert any(event.name == 'xxx' for event in events)
        assert any(event.is_dir for event in events)
    curio.run(main())

def test_interface(tmpdir):
    m = Monitor()
    with pytest.raises(TypeError):
        m.add_watch(str(tmpdir), "xxxx")
    with pytest.raises(TypeError):
        m.add_watch(1234, 0)
    p = Path(str(tmpdir))
    m.add_watch(p, 1)
    m.add_watch(str(tmpdir), EVENTS.IN_CREATE)
    m.add_watch(str(tmpdir), EVENTS.IN_DELETE_SELF,
            replace_existing=True)
    async def do_watch():
        async with m as events:
            assert all(event.tp != EVENTS.IN_CREATE for event in
                    events)
            assert any(event.tp == EVENTS.IN_DELETE_SELF for event in
                    events)
            print(events[0])
    async def main():
        t = await curio.spawn(do_watch())
        with (p/'xxx').open('a'):
            pass
        (p/'xxx').unlink()
        p.rmdir()
        await t.join()
    curio.run(main())








