# -*- coding: utf-8 -*-
"""
Moonitor to watch inotify events

Created on Sun Jun 26 18:34:29 2016

@author: Zahari Kassabov
"""
import errno
import struct
from collections import Sequence
from functools import reduce
import operator
import pathlib

import curio
from curio import io

from .inotify import lib as C
from .inotify import ffi
from . import constants

def errno_code():
    return errno.errorcode[ffi.errno]



fields = ('wd', 'i'), ('mask', 'I'), ('cookie', 'I'), ('len', 'I')
name = ('name', 's')
fmt = ''.join(field[1] for field in fields)
evt_head_size = struct.calcsize(fmt)

def _add_flags(flags):
    return reduce(operator.or_, flags)


def unpack_inotify_events(buffer):
    offset = 0
    events = []
    while True:
        wd, mask, cookie, l = struct.unpack_from(fmt, buffer, offset=offset)
        offset += evt_head_size
        if l>0:
            name = struct.unpack_from('%ds'%l, buffer, offset=evt_head_size)[0]
            name = name[:name.index(b'\0')].decode()
        else:
            name = None
        offset += l
        events.append(Event(wd, mask, cookie, name))
        if offset==len(buffer):
            break
        if offset > len(buffer):
            raise ValueError("Corrupted inotify event")
    return events

def parse_event_mask(mask):
    if mask & constants.RETURN_FLAGS.IN_Q_OVERFLOW:
        raise OSError("inotify queue overflow")
    if mask & constants.RETURN_FLAGS.IN_ISDIR:
        is_dir = True
    else:
        is_dir = False
    tps = (*constants.REAL_EVENTS, constants.RETURN_FLAGS.IN_UNMOUNT,
            constants.RETURN_FLAGS.IN_IGNORED)
    try:
        tp = next(evt for evt in tps if evt & mask)
    except StopIteration as e:
        tp = None
    return tp, is_dir





class Event:
    def __init__(self, wd, mask, cookie, name):
        self.wd = wd
        self.mask = mask
        self.cookie = cookie
        self.name = name

        tp, is_dir = parse_event_mask(mask)
        self.tp = tp
        self.is_dir = is_dir


    def __str__(self):
        return '%s: %s'% (self.tp, self.name if self.name else '.')



class Monitor:
    def __init__(self):
        self._fd = C.inotify_init1(0)
        if self._fd < 0:
            raise OSError("Could not initialize inotify: error %s"
                          % errno_code())
        self._buffer = open(self._fd, 'rb')
        #Makes buffer nonblocking
        self.stream = io.FileStream(self._buffer)

    async def next_events(self):
        data = await self.stream.read()
        return unpack_inotify_events(data)

    async def __aenter__(self):
        return await self.next_events()

    async def __aexit__(self, *exc_info):
        await self.stream.close()

    def __aiter__(self):
        return self

    async def __anext__(self):
        return (await self.next_events())


    def add_watch(self, filename, events, *, exclude_unlink=False,
                  follow_symlinks=True,
                  oneshot=False,
                  replace_existing=False):
        """Watch the filename for the given events. The defaults differ from
        inotify in that if a filename is already being watched, this call will
        add the new events instead of replacing them.
        """
        if isinstance(events, Sequence):
            mask = _add_flags(events)
        elif not isinstance(events, int):
            raise TypeError("Unrecognized format for mask")
        else:
            mask = events
        if exclude_unlink:
            mask |= constants.WATCH_FLAGS.IN_EXCL_UNLINK
        if not follow_symlinks:
            mask |= constants.WATCH_FLAGS.IN_DONT_FOLLOW
        if oneshot:
            mask |= constants.WATCH_FLAGS.IN_ONESHOT
        if not replace_existing:
            mask |= constants.WATCH_FLAGS.IN_MASK_ADD
        if isinstance(filename, str):
           filename = filename.encode()
        #TODO: Use new path protocol when available
        elif isinstance(filename, pathlib.Path):
            filename = str(filename).encode()
        elif not isinstance(filename, bytes):
            raise TypeError("Unrecognized format for filename")
        wd = C.inotify_add_watch(self._fd, filename, mask)
        if wd == -1:
            raise OSError("Could not add watch. Error: %s"%
                    errno_code())


    def close(self):
        self._buffer.close()

    def __del__(self):
        self.close()


def watch(*args, **kwargs):
    m = Monitor()
    m.add_watch(*args, **kwargs)
    return m

