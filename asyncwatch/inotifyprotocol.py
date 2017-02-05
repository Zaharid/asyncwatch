# -*- coding: utf-8 -*-
"""
Parse events from the inotify protocol, IO independent.

@author: Zahari Kassabov
"""
from __future__ import generator_stop
import struct

from asyncwatch import constants
from asyncwatch.exceptions import InotifyError, InotifyQueueOverflow

fields = ('wd', 'i'), ('mask', 'I'), ('cookie', 'I'), ('len', 'I')
name = ('name', 's')
fmt = ''.join(field[1] for field in fields)
evt_head_size = struct.calcsize(fmt)

def unpack_inotify_events(buffer):
    """Yield each of the inotify :class:`Event`
    instances present in the buffer."""
    offset = 0
    while True:
        wd, mask, cookie, l = struct.unpack_from(fmt, buffer, offset=offset)
        offset += evt_head_size
        if l>0:
            name = struct.unpack_from(f'{l}s', buffer, offset=offset)[0]
            name = name[:name.index(b'\0')].decode()
        else:
            name = None
        offset += l
        yield Event(wd, mask, cookie, name)

        if offset==len(buffer):
            break
        if offset > len(buffer):
            raise InotifyError("Corrupted inotify event")

def parse_event_mask(mask):
    """Given the mask of the inotify envent, return a tuple tp, is_dir
    where tp is one of :const:`constants.EVENT_TYPES` and is_dir is whether the
    event matches :const:`constants.RETURN_FLAGS.ISDIR`.

    May raise a ``InotifyQueueOverflow`` if the inotify queue is full
    or an ``InotifyError`` if the event is unknown.
    """
    if mask & constants.RETURN_FLAGS.Q_OVERFLOW:
        raise InotifyQueueOverflow()
    is_dir =  mask & constants.RETURN_FLAGS.ISDIR

    try:
        tp = next(tp for tp in constants.EVENT_TYPES if tp & mask)
    except StopIteration as e:
        raise InotifyError(f"Unknown inotify event with mask: 0x{mask:08x}")

    return tp, is_dir


class Event:
    """A class representing an inotify event. The properties "
    "``wd``, ``mask``, ``cookie`` and ``name`` are verbatin
    from the returned value of the
    C API.

    The properties ``tp`` and `is_dir` are the output of
    :func:`parse_event_mask`.
    """
    def __init__(self, wd, mask, cookie, name):
        self.wd = wd
        self.mask = mask
        self.cookie = cookie
        self.name = name

        tp, is_dir = parse_event_mask(mask)
        self.tp = tp
        self.is_dir = is_dir

    def __str__(self):
        return f'{str(self.tp)}: {self.name if self.name else None}'