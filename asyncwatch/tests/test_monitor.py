import os
from pathlib import Path

import pytest
import curio

from asyncwatch import Monitor, watch, EVENTS, NoMoreWatches


async def touch(p):
    new_path = p/'xxx'
    async with curio.aopen(str(new_path), 'a') as f:
        pass
    return new_path


def test_iter(tmpdir):
    p = Path(str(tmpdir))
    async def do_watch():
        count = 0
        async for events in  watch(str(p), EVENTS.CREATE):
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
        monitor = watch(str(tmpdir), EVENTS.DELETE, oneshot=True)
        async with monitor as events:
            assert any(event.tp ==  EVENTS.DELETE for event in
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
    with pytest.raises(TypeError):
        m.add_watch('/', None)

def test_several(tmpdir):
    m = Monitor()
    m.add_watch(str(tmpdir), (EVENTS.ACCESS, EVENTS.CREATE))
    async def main():
        tmpdir.mkdir('xxx')
        events = await m.next_events()
        assert any(event.name == 'xxx' for event in events)
        assert any(event.is_dir for event in events)
    curio.run(main())

def test_symlinks(tmpdir):
    m1 = Monitor()
    m2 = Monitor()
    root_path = Path(str(tmpdir))

    watch_path = root_path / 'dir'
    watch_path.mkdir()

    f = watch_path / 'file'
    f.touch()
    link = watch_path / 'link'
    link.symlink_to(f)

    m1.add_watch(link, EVENTS.ALL_EVENTS,
            follow_symlinks=False)
    m2.add_watch(link, EVENTS.ALL_EVENTS)
    async def do_watch_m1():
        async with m1:
            raise RuntimeError()

    async def do_watch_m2(t):
        async with m2:
            await t.cancel()



    async def main():
        t1 = await curio.spawn(curio.timeout_after(2, do_watch_m1()))
        t2 = await curio.spawn(curio.timeout_after(2, do_watch_m2(t1)))
        with link.open('a') as wr:
            wr.write("Hello")
        await t2.join()
        with pytest.raises(curio.TaskError):
            await t1.join()


    curio.run(main(), with_monitor=True)

def test_interface(tmpdir):
    m = Monitor()
    with pytest.raises(TypeError):
        m.add_watch(str(tmpdir), "xxxx")
    with pytest.raises(TypeError):
        m.add_watch(1234, 0)
    p = Path(str(tmpdir))
    m.add_watch(p, 1)
    m.add_watch(str(tmpdir), EVENTS.CREATE)
    m.add_watch(str(tmpdir), EVENTS.DELETE_SELF,
            replace_existing=True)
    async def do_watch():
        async with m as events:
            assert all(event.tp != EVENTS.CREATE for event in
                    events)
            assert any(event.tp == EVENTS.DELETE_SELF for event in
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

def test_remove(tmpdir):
    s = str(tmpdir)
    p = Path(s)
    subpaths = []
    m = Monitor(error_empty=True)
    for i in '1234':
        subpath = p/i
        subpath.touch()
        m.add_watch(subpath, EVENTS.DELETE_SELF)
        subpaths.append(subpath)

    assert(len(m._watches) == len(subpaths) == len(m.active_watches()))
    wd = m.add_watch(p, EVENTS.DELETE_SELF)

    it = iter(subpaths)
    def delpath():
        try:
            next(it).unlink()
        except StopIteration:
            m.remove_watch(wd)

    async def do_watch():
        try:
            async for events in m:
                delpath()
        except NoMoreWatches:
            return

    async def main():
        t = await curio.spawn(curio.timeout_after(2, do_watch()))
        delpath()
        await t.join()
    curio.run(main())
    with pytest.raises(ValueError):
        m.remove_watch(wd)
    assert not m._watches


