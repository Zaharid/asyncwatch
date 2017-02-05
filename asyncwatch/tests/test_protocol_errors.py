import struct

import pytest

from asyncwatch import inotifyprotocol
from asyncwatch.constants import EVENTS, RETURN_FLAGS
from asyncwatch import exceptions

def test_corrupted():
    wd = 1
    mask = EVENTS.MODIFY
    filename = b'xx\0'
    b = struct.pack(inotifyprotocol.fmt, wd, mask, 0, len(filename)) + filename
    evt = list(inotifyprotocol.unpack_inotify_events(b))[0]
    assert evt.name == 'xx'
    assert evt.tp == EVENTS.MODIFY
    with pytest.raises(exceptions.InotifyError):
        inotifyprotocol.Event(wd, 0, 0, None)
    with pytest.raises(exceptions.InotifyQueueOverflow):
        inotifyprotocol.Event(wd, RETURN_FLAGS.Q_OVERFLOW, 0, None)
