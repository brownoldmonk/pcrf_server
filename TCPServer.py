import socket
import multiprocessing
import subprocess
import struct
import fcntl
import os
import heapq
import collections
import time
import pickle
import sys
import select
import json

from util import add_accept_handler, add_timout_handler, add_worker_read_handler, add_worker_write_handler, add_recv_handler, add_send_handler, _ERRNO_WOULDBLOCK, add_stdin_handler
import Diameter
from PollIOLoop import PollIOLoop

IN_POLL = 0
OUT_POLL = 1

class TCPServer(object):
    def __init__(self, addr, port, ioloop, dict_file, reply_file=None):
        self.addr = addr
        self.port = port
        self.io_loop = ioloop
        self.sock = None
        self._conns = {}
        self.dict_file = dict_file
        self.reply_file = reply_file
        Diameter.init_dict(dict_file)
        if reply_file is not None:
            Diameter.init_template(reply_file)

    def fileno(self):
        if self.sock:
            return self.sock.fileno()
        return None

    def listen(self, backlog):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(0)
        self.sock.bind((self.addr, self.port))
        self.sock.listen(backlog)

        add_accept_handler(self.sock, self._handle_connection,
                           io_loop=self.io_loop)

    def _handle_connection(self, connection, address):
        if self.reply_file:
            self._conns[str(connection.fileno())] = TCPConn(connection, address, self.io_loop,
                                                        self.dict_file, self.reply_file)
        else:
            self._conns[str(connection.fileno())] = IOConn(connection, address, self.io_loop)

class BaseConn(object):
    def __init__(self, conn, addr, ioloop):
        self.conn = conn
        self.conn.setblocking(0)
        self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.addr = addr
        self.io_loop = ioloop
        add_recv_handler(conn, self._handle_recv, ioloop)

    def _handle_recv(self, data):
        raise NotImplementedError()

class IOConn(BaseConn):
    def __init__(self, conn, addr, ioloop):
         super(IOConn, self).__init__(conn, addr, ioloop)
         ioloop.add_handler(0, self.handle_stdin_read, PollIOLoop.READ)
         #add_stdin_handler(0, self.handle_stdin_read, ioloop)
         #ioloop._impl.register(0, PollIOLoop.READ)
         #ioloop._impl.register(sys.stdin, select.EPOLLIN)

         self.recv_pack = None

    def _handle_recv(self, data):
        self.recv_pack = data

    def handle_stdin_read(self, fd, events):
        length = os.read(fd, 4)
        length = struct.unpack('I', length)[0]
        with open('/tmp/xxxx.debug', 'a') as f:
            f.write(str(length)+'\n')
        #os.read(fd, 1)
        desc = os.read(fd, length + 1)
        #os.read(fd, 1)
        #desc = struct.unpack(str(length + 2) + 's', desc)
        with open('/tmp/xxxx.debug', 'a') as f:
            f.write(str(len(desc)))
        #desc = pickle.loads(desc[1:-1])
        desc = json.loads(desc[:-1])
        with open('/tmp/xxxx.debug', 'a') as f:
            f.write(repr(desc))
        reply = Diameter.gen_reply(self.recv_pack, desc)
        self.conn.sendall(reply)


class TCPConn(object):
    def __init__(self, conn, addr, ioloop, dict_file, reply_file):
        self.conn = conn
        self.conn.setblocking(0)
        self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.addr = addr
        self.io_loop = ioloop
        self.workers = []
        self.worker_number = multiprocessing.cpu_count()
        if self.worker_number > 1:
            self.worker_number -= 1
        self.spliter = Parser(ioloop, self)
        self.recv_buf = ''
        self.send_data = []
        self.first_time = True
        self.write_status = OUT_POLL
        self.init_worker(dict_file, reply_file)
        add_recv_handler(conn, self._handle_recv, ioloop)

        self.recv_cnt = 0
        self.send_cnt = 0
        self.write_cnt = 0

    def _handle_recv(self, data):
        #print "recv"
        if data is None:
            self.conn.close()
            #self.close_worker()
            return

        #return
        self.spliter.add_task(data)
        self.spliter.run(True)
        #msg = self.recv_buf + data
        #while True:
        #    cmd_code, length, pack = Diameter.parse(msg)
        #    if pack is None:
        #        break

        #    task = struct.pack('II' + str(length+2) + 's', cmd_code, length, '\n' + pack + '\n')
        #    worker = heapq.heappop(self.workers)
        #    worker.add_task(task)
        #    self.workers.append(worker)

        #    msg = msg[length:]
        #    self.recv_cnt += 1
        #    #print len(msg)

        #if msg:
        #    self.recv_buf = msg
        #else:
        #    self.recv_buf = ''

        if self.first_time:
            print "first", time.time()
            add_send_handler(self.conn, self._handle_send, self.io_loop)
            self.first_time = False
            self.write_status = IN_POLL

    def handle_spliter_reply(self, data_list):
        for task in data_list:
            worker = heapq.heappop(self.workers)
            worker.add_task(task)
            self.workers.append(worker)

        for idx in xrange(self.worker_number):
            if self.workers[idx].write_status == OUT_POLL:
                self.workers[idx].run()

    def handle_worker_reply(self, data):
        #print repr(data)
        timeout_msg = {}
        for timeout, msg in data:
            if timeout == 0:
                self.send_data.append(msg)
            elif str(timeout) in timeout_msg:
                timeout_msg[str(timeout)] += msg
            else:
                timeout_msg[str(timeout)] = msg

        for timeout, value in timeout_msg:
            add_timout_handler(int(timeout), self._handle_send, value, self.io_loop)
        self._handle_send(self_call=True)

    def _handle_send(self, data=None, self_call=False):
        #print "send", len(self.send_data)
        #print self.send_data
        # call from self
        if self_call and self.write_status == IN_POLL:
            return
        if data is not None:
            self.send_data.append(data)
        if not self.send_data:
            if self.write_status == IN_POLL:
                self.io_loop.remove_handler(self.conn.fileno(), PollIOLoop.WRITE)
                self.write_status = OUT_POLL
            return

        #print "before send", len(self.send_data)
        need_add = False
        while self.send_data:
            data = self.send_data.pop(0)
            try:
                self.conn.sendall(data)
                #print "send data", len(data)
                data = None
                self.send_cnt += 1
            except socket.error as e:
                if e.args[0] in _ERRNO_WOULDBLOCK:
                    need_add = True
                    break
                else:
                    raise
        if data:
            self.send_data.insert(0, data)

        #print "after send", len(self.send_data)
        #print "after send", self.send_cnt
        if need_add and self.write_status == OUT_POLL:
            add_send_handler(self.conn, self._handle_send, self.io_loop)
            self.write_status = IN_POLL
        elif self.write_status == IN_POLL and not need_add:
            self.io_loop.remove_handler(self.conn.fileno(), PollIOLoop.WRITE)
            self.write_status = OUT_POLL

        if self.send_cnt == 100000:
            print "Send", self.send_cnt, time.time()
        #print "Send", self.send_cnt, time.time()


    def init_worker(self, dict_file, reply_file):
        for _ in xrange(self.worker_number):
            worker = Worker(dict_file, reply_file, self.io_loop, self)
            self.workers.append(worker)

class Worker(object):
    def __init__(self, dict_file, reply_file, ioloop, conn):
        self.conn = conn
        self.work_load = 0
        cmd = ['python', 'worker.py', '--dict', dict_file, '--reply', reply_file]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                  stderr=subprocess.PIPE, close_fds=True)
        read_fd = self.proc.stderr.fileno()
        fl = fcntl.fcntl(read_fd, fcntl.F_GETFL)
        fcntl.fcntl(read_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        self.read_fd = read_fd
        ioloop.add_handler(read_fd, self.read_handler, PollIOLoop.READ)

        write_fd = self.proc.stdin.fileno()
        fl = fcntl.fcntl(write_fd, fcntl.F_GETFL)
        fcntl.fcntl(write_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        self.write_fd = write_fd
        self.task_list = collections.deque()
        self.io_loop = ioloop
        self.write_status = OUT_POLL

        self.read_header = ''
        self.read_body = None
        self.read_todo = 8
        self.read_header_timeout = 0
        self.read_header_len = 0

    def read_handler(self, fd, event):
        #print "worker read"
        ret = []
        while 1:
            try:
                chunk = os.read(fd, self.read_todo)
            except OSError as e:
                if e.errno in _ERRNO_WOULDBLOCK:
                    break
                else:
                    raise

            if self.read_body is None:
                self.read_header += chunk
            else:
                self.read_body += chunk

            # sanity check
            if len(self.read_header) == 8 and self.read_body is None:
                result = struct.unpack('II', self.read_header)
                self.read_header_timeout = result[0]
                self.read_header_len = result[1]
                self.read_todo = result[1]
                self.read_body = ''
            elif len(self.read_header) < 8:
                self.read_todo = 8 - len(self.read_header)
            elif len(self.read_body) < self.read_header_len:
                self.read_todo = self.read_header_len - len(self.read_body)
            else:
                ret.append((self.read_header_timeout, self.read_body))
                self.read_header = ''
                self.read_body = None
                self.read_todo = 8
                self.read_header_timeout = 0
                self.read_header_len = 0

        self.work_load -= len(ret)
        #print "woker done", len(ret)
        self.conn.handle_worker_reply(ret)

    def add_task(self, task):
        self.task_list.append(task)
        self.work_load += 1

    def run(self):
        task = None
        add_to_poll = False
        #print "before worker push task", len(self.task_list)
        while self.task_list:
            task = self.task_list.popleft()
            #print "write", repr(task)
            try:
                length = os.write(self.write_fd, task)
                if length != len(task):
                    self.task_list.appendleft(task[length:])
                task = None
            except OSError as e:
                if e.errno in _ERRNO_WOULDBLOCK:
                    add_to_poll = True
                    break
                else:
                    raise
        if task:
            self.task_list.appendleft(task)

        self.work_load = len(self.task_list)

        #print "after worker push task", len(self.task_list)
        if add_to_poll and self.write_status == OUT_POLL:
            self.write_status = IN_POLL
            add_worker_write_handler(self.write_fd, self.run, self.io_loop)
        elif self.write_status == IN_POLL and not add_to_poll:
            self.write_status = OUT_POLL
            self.io_loop.remove_handler(self.write_fd, PollIOLoop.WRITE)

    def __lt__(self, other):
        return self.work_load < other.work_load

    def __le__(self, other):
        return self.work_load <= other.work_load

class Parser(object):
    def __init__(self, ioloop, conn):
        self.conn = conn
        cmd = ['python', 'spliter.py']
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                  stderr=subprocess.PIPE, close_fds=True)
        read_fd = self.proc.stderr.fileno()
        fl = fcntl.fcntl(read_fd, fcntl.F_GETFL)
        fcntl.fcntl(read_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        self.read_fd = read_fd
        ioloop.add_handler(read_fd, self.read_handler, PollIOLoop.READ)

        write_fd = self.proc.stdin.fileno()
        fl = fcntl.fcntl(write_fd, fcntl.F_GETFL)
        fcntl.fcntl(write_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        self.write_fd = write_fd
        self.task_list = collections.deque()
        self.io_loop = ioloop
        self.write_status = OUT_POLL

        self.read_header = ''
        self.read_body = None
        self.read_todo = 4
        self.read_header_len = 0

    def read_handler(self, fd, event):
        #print "spliter read"
        ret = []
        while 1:
            try:
                chunk = os.read(fd, self.read_todo)
            except OSError as e:
                if e.errno in _ERRNO_WOULDBLOCK:
                    break
                else:
                    raise

            if self.read_body is None:
                self.read_header += chunk
            else:
                self.read_body += chunk

            #print len(chunk), len(self.read_header)
            # sanity check
            if len(self.read_header) == 4 and self.read_body is None:
                result = struct.unpack('I', self.read_header)
                self.read_header_len = result[0]
                self.read_todo = result[0]
                self.read_body = ''
            elif len(self.read_header) < 4:
                self.read_todo = 4 - len(self.read_header)
            elif len(self.read_body) < self.read_header_len:
                self.read_todo = self.read_header_len - len(self.read_body)
            else:
                #print "spliter", self.read_header_len
                ret.append(self.read_body)
                self.read_header = ''
                self.read_body = None
                self.read_todo = 4
                self.read_header_len = 0

        #print "got worker task", len(ret)
        self.conn.handle_spliter_reply(ret)

    def add_task(self, data):
        task = struct.pack('I' + str(len(data)+2) + 's', len(data), '\n' + data + '\n')
        self.task_list.append(task)

    def run(self, self_call=False):
        if self_call and self.write_status == IN_POLL:
            return
        task = None
        add_to_poll = False
        #print "before task", len(self.task_list)
        while self.task_list:
            task = self.task_list.popleft()
            try:
                length = os.write(self.write_fd, task)
                if length != len(task):
                    self.task_list.appendleft(task[length:])
                task = None
            except OSError as e:
                if e.errno in _ERRNO_WOULDBLOCK:
                    add_to_poll = True
                    break
                else:
                    raise
        if task:
            self.task_list.appendleft(task)

        #print "after task", len(self.task_list)
        if add_to_poll and self.write_status == OUT_POLL:
            self.write_status = IN_POLL
            add_worker_write_handler(self.write_fd, self.run, self.io_loop)
        elif self.write_status == IN_POLL and not add_to_poll:
            self.write_status = OUT_POLL
            self.io_loop.remove_handler(self.write_fd, PollIOLoop.WRITE)
