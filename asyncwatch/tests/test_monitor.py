import os
from pathlib import Path

import pytest
import curio

from asyncwatch import Monitor, watch, EVENTS, NoMoreWatches
from asyncwatch.tests.utils import tmp


async def touch(p):
    new_path = p/'xxx'
    async with curio.aopen(new_path, 'a'):
        pass
    return new_path


def test_iter(tmp):
    p = tmp
    async def do_watch():
        count = 0
        async for event in  watch(p, EVENTS.CLOSE):
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


def test_context(tmp):
    async def do_watch():
        monitor = watch(tmp, EVENTS.DELETE, oneshot=True)
        async with monitor as event:
            assert event.tp ==  EVENTS.DELETE
        with pytest.raises(OSError):
            os.fstat(monitor._fd)

    async def main():
        t = await curio.spawn(do_watch())
        np = await touch(tmp)
        Path(np).unlink()
        await t.join()

    curio.run(main())


def kernel_version_tuple():
    import platform
    def maybe_int(x):
        try:
            return int(x)
        except:
            return x
    return tuple(maybe_int(x) for x in platform.release().split('.'))


@pytest.mark.xfail(kernel_version_tuple() < (4,2),
        reason="Old kernel version. See: "
        "https://lkml.org/lkml/2015/6/30/472")
def test_bad():
    m = Monitor()
    with pytest.raises(OSError):
        m.add_watch('/', 123212313)
    with pytest.raises(TypeError):
        m.add_watch('/', None)

def test_several(tmpdir):
    m = Monitor()
    m.add_watch(tmpdir, (EVENTS.ACCESS, EVENTS.CREATE))
    async def main():
        tmpdir.mkdir('xxx')
        async for event in m.next_events():
            assert event.name == 'xxx'
            assert event.is_dir
            assert str(event) in ('CREATE: xxx', 'ACCESS: xxx')
    curio.run(main())

def test_symlinks(tmp):
    m1 = Monitor()
    m2 = Monitor()
    root_path = tmp

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
        async with m1: # pragma: no cover
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

def test_interface(tmp):
    m = Monitor()
    with pytest.raises(TypeError):
        m.add_watch(tmp, "xxxx")
    with pytest.raises(TypeError):
        m.add_watch(1234, 0)
    p = tmp
    m.add_watch(p, 1)
    m.add_watch(tmp, EVENTS.CREATE)
    m.add_watch(tmp, EVENTS.DELETE_SELF,
            replace_existing=True)
    async def do_watch():
        async for event in m.next_events():
            assert event.tp != EVENTS.CREATE


    async def main():
        t = await curio.spawn(do_watch())
        with (p/'xxx').open('a'):
            pass
        (p/'xxx').unlink()
        p.rmdir()
        await t.join()
    curio.run(main())

def test_filters(tmp):
    p = tmp
    m = watch(p, EVENTS.ALL_EVENTS, filter="abc*d")
    async def do_watch():
       async for event in m.next_events():
            assert event.name == "abcXXd"

    async def main():
        t = await curio.spawn(curio.timeout_after(1,do_watch()))
        (p/"xyz").touch()
        (p/"abcXXd").touch()
        await t.join()

        (p/"xyz").touch()
        #Cover the case where all the first events are filtered out
        t = await curio.spawn(do_watch())
        (p/'XXX').touch()
        await curio.sleep(0)
        (p/"abcXXd").touch()
        await t.join()


    curio.run(main())

def test_remove(tmp):
    p = tmp
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
            async for event in m:
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
