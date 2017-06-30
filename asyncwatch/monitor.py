# -*- coding: utf-8 -*-
"""
Moonitor to watch inotify events

Created on Sun Jun 26 18:34:29 2016

@author: Zahari Kassabov
"""
from __future__ import generator_stop
import errno
from collections import Sequence, namedtuple
import fnmatch
import os
import operator
from functools import reduce

from curio import io

from .inotify import lib as C
from .inotify import ffi
from . import exceptions
from . import constants
from .inotifyprotocol import unpack_inotify_events

__all__ = ('Monitor', 'watch')

def errno_code():
    return errno.errorcode[ffi.errno]

WatchSpec =  namedtuple('WatchSpec', ('name', 'mask', 'filter'))


def _add_flags(flags):
    return reduce(operator.or_, flags)


class Monitor:
    """A monitor contains zero or more watches."""
    def __init__(self, error_empty=False):
        """...
        error_empty: If the watch count reaches 0 while waiting for
        events, raise an exception. This is useful to avoid accidental
        deadlocks.
        """
        #The python in conda fails for thos and it is not important
        #enough to care about it that much.
        #self._fd = C.inotify_init1(os.O_CLOEXEC)
        self._fd = C.inotify_init1(0)

        if self._fd < 0:
            raise OSError(f"Could not initialize inotify: error {errno_code()}")
        self._buffer = open(self._fd, 'rb')
        #Makes buffer nonblocking already
        self.stream = io.FileStream(self._buffer)
        self._watches = {}
        self.error_empty = error_empty

    async def next_events(self):
        """Wait until there is at least one event passing the filters, and
        yield all the received events,
        from any of the active watches.
        The events that do not match the filers
        (and only if a filter is set for the watch) are dropped.
        Yields at least one event.
       """
        if self.error_empty and not self._watches:
            raise exceptions.NoMoreWatches()
        data = await self.stream.read()
        events = unpack_inotify_events(data)
        yield_one = False
        for event in events:
            if event.tp == constants.RETURN_FLAGS.IGNORED:
                self._watches.pop(event.wd, None)
            else:
                watch = self._watches[event.wd]
                if (watch.filter is not None and
                    (not event.name or
                     not fnmatch.fnmatch(event.name, watch.filter))
                    ):
                    continue
                yield event
                yield_one = True

        #No event passes the filters so we fetch more
        if not yield_one:
            async for event in self.next_events():
                yield event

    async def _loop(self):
        while True:
            async for evt in self.next_events():
                yield evt

    async def __aenter__(self):
        async for e in self.next_events():
            return e

    async def __aexit__(self, *exc_info):
        await self.stream.close()

    def __aiter__(self):
        return  self._loop()

    def add_watch(self, filename, events, *, exclude_unlink=False,
                  follow_symlinks=True,
                  oneshot=False,
                  replace_existing=False, filter=None):
        """Watch the filename for the given events. The defaults differ from
        inotify in that if a filename is already being watched, this call will
        add the new events instead of replacing them.

        events can be either an integer representing the mask passed to
        ``inotify_add_watch`` or a sequence of Constants.Events.

        ``exclude_unlink`, ``follow_symlinks`` and ``oneshot`` set the
        corrsponding flags to be appended to the mask.

        ``filter`` is a glob mask. If set onle the events with `name` matching
        the filter will be forwarded, and the rest will be droped.
        """
        if isinstance(events, Sequence):
            mask = _add_flags(events)
        elif not isinstance(events, int):
            raise TypeError("Unrecognized format for mask")
        else:
            mask = events
        if exclude_unlink:
            mask |= constants.WATCH_FLAGS.EXCL_UNLINK
        if not follow_symlinks:
            mask |= constants.WATCH_FLAGS.DONT_FOLLOW
        if oneshot:
            mask |= constants.WATCH_FLAGS.ONESHOT
        if not replace_existing:
            mask |= constants.WATCH_FLAGS.MASK_ADD

        wd = C.inotify_add_watch(self._fd, os.fsencode(filename), mask)
        if wd == -1:
            raise exceptions.InotifyError(
                f"Could not add watch. Error: {errno_code()}."
            )
        watch_spec = WatchSpec(filename, mask, filter)
        self._watches[wd] = watch_spec
        return wd

    def remove_watch(self, wd):
        if wd not in self._watches:
            raise ValueError("Invalid watch descriptor")
        val = C.inotify_rm_watch(self._fd, wd)
        if val != 0:
            raise exceptions.InotifyError(
                f"Could not remove watch. Error: {errno_code()}."
            )
        del self._watches[wd]

    def active_watches(self):
        """Return a copy of the active watches"""
        return self._watches.copy()

    def close(self):
        self._buffer.close()


def watch(*args, **kwargs):
    """Convenience method to start a :class:`Monitor` with one wtcher.
    The arguments are passed to the :attr:`Monitor.add_watch` method.
    The monitor is started with the ``error_empty`` flag set."""
    m = Monitor(error_empty=True)
    m.add_watch(*args, **kwargs)
    return m

