import socket
import logging
import errno
import os
import struct
import fcntl



app_log = logging.getLogger("pcrf")
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
app_log.addHandler(ch)

# These errnos indicate that a non-blocking operation must be retried
# at a later time.  On most platforms they're the same value, but on
# some they differ.
_ERRNO_WOULDBLOCK = (errno.EWOULDBLOCK, errno.EAGAIN)

if hasattr(errno, "WSAEWOULDBLOCK"):
    _ERRNO_WOULDBLOCK += (errno.WSAEWOULDBLOCK,)

# These errnos indicate that a connection has been abruptly terminated.
# They should be caught and handled less noisily than other errors.
_ERRNO_CONNRESET = (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE,
                    errno.ETIMEDOUT)

if hasattr(errno, "WSAECONNRESET"):
    _ERRNO_CONNRESET += (errno.WSAECONNRESET, errno.WSAECONNABORTED, errno.WSAETIMEDOUT)

# More non-portable errnos:
_ERRNO_INPROGRESS = (errno.EINPROGRESS,)

if hasattr(errno, "WSAEINPROGRESS"):
    _ERRNO_INPROGRESS += (errno.WSAEINPROGRESS,)

def errno_from_exception(e):
    """Provides the errno from an Exception object.

    There are cases that the errno attribute was not set so we pull
    the errno out of the args but if someone instatiates an Exception
    without any args you will get a tuple error. So this function
    abstracts all that behavior to give you a safe way to get the
    errno.
    """

    if hasattr(e, 'errno'):
        return e.errno
    elif e.args:
        return e.args[0]
    else:
        return None

def add_accept_handler(sock, callback, io_loop):
    from PollIOLoop import PollIOLoop
    """Adds an `.IOLoop` event handler to accept new connections on ``sock``.

    When a connection is accepted, ``callback(connection, address)`` will
    be run (``connection`` is a socket object, and ``address`` is the
    address of the other end of the connection).  Note that this signature
    is different from the ``callback(fd, events)`` signature used for
    `.IOLoop` handlers.
    """
    def accept_handler(fd, events):
        try:
            connection, address = sock.accept()
        except socket.error as e:
            # _ERRNO_WOULDBLOCK indicate we have accepted every
            # connection that is available.
            if errno_from_exception(e) in _ERRNO_WOULDBLOCK:
                return
            # ECONNABORTED indicates that there was a connection
            # but it was closed while still in the accept queue.
            # (observed on FreeBSD).
            if errno_from_exception(e) == errno.ECONNABORTED:
                raise
        callback(connection, address)
    io_loop.add_handler(sock.fileno(), accept_handler, PollIOLoop.READ)

def add_timout_handler(timeout, callback, args, io_loop):
    def timeout_handler():
        callback(args)
    io_loop.add_timeout(timeout, timeout_handler)

def add_recv_handler(sock, callback, io_loop):
    from PollIOLoop import PollIOLoop
    def recv_handler(fd, events):
        data = ''
        while True:
            try:
                chunk = sock.recv(102400)
            except socket.error as e:
                if e.args[0] in _ERRNO_WOULDBLOCK:
                    break
                else:
                    raise
            if not chunk:
                data = None
                break
            data += chunk
        #if data is not None:
        #    print len(data)
        callback(data)

    io_loop.add_handler(sock.fileno(), recv_handler, PollIOLoop.READ)

def add_worker_read_handler(worker_fd, callback, io_loop):
    from PollIOLoop import PollIOLoop
    def worker_read_handler(fd, events):
        while True:
            try:
                chunk = os.read(fd, 8)
            except OSError as e:
                if e.errno in _ERRNO_WOULDBLOCK:
                    break
                else:
                    raise
            #print repr(chunk)
            result = struct.unpack('II', chunk)
            data = os.read(fd, result[1])
            callback(result[0], data)

    #fl = fcntl.fcntl(worker_fd, fcntl.F_GETFL)
    #fcntl.fcntl(worker_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    io_loop.add_handler(worker_fd, worker_read_handler, PollIOLoop.READ)

def add_worker_write_handler(worker_fd, callback, io_loop):
    from PollIOLoop import PollIOLoop
    def worker_write_handler(fd, events):
        callback()

    #fl = fcntl.fcntl(worker_fd, fcntl.F_GETFL)
    #fcntl.fcntl(worker_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    io_loop.add_handler(worker_fd, worker_write_handler, PollIOLoop.WRITE)

def add_send_handler(sock, callback, io_loop):
    from PollIOLoop import PollIOLoop
    def send_handler(fd, events):
        callback()
    io_loop.add_handler(sock.fileno(), send_handler, PollIOLoop.WRITE)

def add_stdin_handler(fd, callback, io_loop):
    from PollIOLoop import PollIOLoop
    def stdin_handler(fd, events):
        callback(fd, events)
    io_loop.add_handler(fd, stdin_handler, PollIOLoop.READ)
