class AsyncWatchError(Exception): pass

class NoMoreWatches(AsyncWatchError): pass

class InotifyError(AsyncWatchError, OSError): pass

class InotifyQueueOverflow(InotifyError): pass