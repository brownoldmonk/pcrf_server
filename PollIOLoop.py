import time
import heapq
import select
import errno
import functools
import numbers

from util import app_log, errno_from_exception

_POLL_TIMEOUT = 3600.0

class PollIOLoop(object):
    # Constants from the epoll module
    _EPOLLIN = 0x001
    _EPOLLPRI = 0x002
    _EPOLLOUT = 0x004
    _EPOLLERR = 0x008
    _EPOLLHUP = 0x010
    _EPOLLRDHUP = 0x2000
    _EPOLLONESHOT = (1 << 30)
    _EPOLLET = (1 << 31)

    # Our events map exactly to the epoll events
    NONE = 0
    READ = _EPOLLIN
    WRITE = _EPOLLOUT
    ERROR = _EPOLLERR | _EPOLLHUP

    def __init__(self):
        self._impl = None
        self._handlers = {}
        self._timeouts = []
        self._events = {}

    def initialize(self):
        self._impl = select.epoll()

    def add_handler(self, fd, handler, events):
        print "add", fd, handler, events
        if str(fd) not in self._handlers:
            self._handlers[str(fd)] = {'handler': {}, 'mask': events | self.ERROR}
            self._handlers[str(fd)]['handler'][str(events)] = handler
            self._impl.register(fd, events | self.ERROR)
        elif str(events) not in self._handlers[str(fd)]['handler']:
            self._handlers[str(fd)]['handler'][str(events)] = handler
            self._impl.modify(fd, events | self._handlers[str(fd)]['mask'])
        #else:
        #    print fd, handler, events
        #    raise RuntimeError('can not add new event to old fd')

    def remove_handler(self, fd, events):
        if str(fd) in self._handlers and str(events) in self._handlers[str(fd)]['handler']:
            print "remove", fd, events
            self._impl.modify(fd, self._handlers[str(fd)]['mask'] & ~events)
            del self._handlers[str(fd)]['handler'][str(events)]
            self._handlers[str(fd)]['mask'] &= ~events

    def add_timeout(self, timeout, callback, *args, **kwargs):
        timeout = _Timeout(
            time.time() + timeout,
            functools.partial(callback, *args, **kwargs),
            self)
        heapq.heappush(self._timeouts, timeout)

    def handle_callback_exception(self, callback):
        """This method is called whenever a callback run by the `IOLoop`
        throws an exception.

        By default simply logs the exception as an error.  Subclasses
        may override this method to customize reporting of exceptions.

        The exception itself is not passed explicitly, but is available
        in `sys.exc_info`.
        """
        app_log.error("Exception in callback %r", callback, exc_info=True)

    def start(self):
        while True:
            callbacks = []

            # Add any timeouts that have come due to the callback list.
            # Do not run anything until we have determined which ones
            # are ready, so timeouts that call add_timeout cannot
            # schedule anything in this iteration.
            if self._timeouts:
                now = time.time()
                while self._timeouts:
                    if self._timeouts[0].deadline <= now:
                        timeout = heapq.heappop(self._timeouts)
                        callbacks.append(timeout.callback)
                        del timeout
                    else:
                        break

            for callback in callbacks:
                callback()

            if self._timeouts:
                # If there are any timeouts, schedule the first one.
                # Use self.time() instead of 'now' to account for time
                # spent running callbacks.
                poll_timeout = self._timeouts[0].deadline - time.time()
                poll_timeout = max(0, min(poll_timeout, _POLL_TIMEOUT))
            else:
                # No timeouts and no callbacks, so use the default.
                poll_timeout = _POLL_TIMEOUT

            #print "time", poll_timeout
           # print self._handlers
            event_pairs = self._impl.poll(poll_timeout)
            #print event_pairs
            # Pop one fd at a time from the set of pending fds and run
            # its handler. Since that handler may perform actions on
            # other file descriptors, there may be reentrant calls to
            # this IOLoop that update self._events
            self._events.update(event_pairs)
            #print self._events
            while self._events:
                fd, events = self._events.popitem()
               # print fd, events
                try:
                    for reg_event, handler_func in self._handlers[str(fd)]['handler'].items():
                        #print reg_event
                        if int(reg_event) & events:
                            handler_func(fd, events)
                except (OSError, IOError) as e:
                    if errno_from_exception(e) == errno.EPIPE:
                        # Happens when the client closes the connection
                        pass
                    else:
                        self.handle_callback_exception(self._handlers.get(fd))
                except Exception:
                    self.handle_callback_exception(self._handlers.get(fd))
            handler_func = None

class _Timeout(object):
    """An IOLoop timeout, a UNIX timestamp and a callback"""

    def __init__(self, deadline, callback, io_loop):
        if not isinstance(deadline, numbers.Real):
            raise TypeError("Unsupported deadline %r" % deadline)
        self.deadline = deadline
        self.callback = callback

    # Comparison methods to sort by deadline. The heapq module uses __le__
    # in python2.5, and __lt__ in 2.6+ (sort() and most other comparisons
    # use __lt__).
    def __lt__(self, other):
        return self.deadline < other.deadline

    def __le__(self, other):
        return self.deadline <= other.deadline
