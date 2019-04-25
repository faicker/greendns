# -*- coding: utf-8 -*-
import sys
import socket
import logging
import errno
from collections import namedtuple
from greendns import ioloop

Addr = namedtuple("Addr", "protocol ip port")

def parse_addr(addrstr):
    addr = addrstr.split(':')
    if len(addr) == 1:
        return Addr('udp', addr[0], 53)
    if len(addr) == 2:
        return Addr('udp', addr[0], int(addr[1]))
    if addr[0] in ('udp', 'tcp'):
        return Addr(addr[0], addr[1], int(addr[2]))
    return None

class BindException(Exception):
    pass

class Error(Exception):
    pass

E_OK = 0
E_FAIL = 1
class ConnError(Error):
    def __init__(self, errcode, errmsg):
        super(ConnError, self).__init__()
        self.errcode = errcode
        self.errmsg = errmsg

    def __str__(self):
        return "(%d, %s)" % (self.errcode, self.errmsg)

class Connection(object):
    def __init__(self, logger=None, io_engine=None):
        self.io_engine = io_engine
        self.remote_addr = None     # meaningless for udp server
        self.bind_addr = None
        self.closed = False
        self.logger = logger if logger else logging.getLogger()

    def run(self):
        self.io_engine.run()

    def stop(self):
        self.io_engine.stop()

class UDPConnection(Connection):
    DEFAULT_UDP_RECV_BUFSIZE = 2048
    def __init__(self, *args, **kwargs):
        super(UDPConnection, self).__init__(*args, **kwargs)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_buffer_size = self.DEFAULT_UDP_RECV_BUFSIZE

    def bind(self, bind_addr):
        try:
            self.sock.bind(bind_addr)
        except socket.error as err:
            self.logger.error("bind failed. error=%s", err)
            self.sock.close()
            raise BindException()
        self.bind_addr = self.sock.getsockname()

    def close(self):
        if not self.closed:
            self.io_engine.on_close_sock(self.sock)
            self.sock.close()
            self.closed = True

    def set_recv_buffer_size(self, size):
        self.recv_buffer_size = size

    # only client of one connection use
    def asend(self, remote_addr, data, on_sent, *args, **kwargs):
        self.remote_addr = remote_addr
        self.io_engine.register(self.sock, ioloop.EV_WRITE,
                                self.__handle_asend,
                                remote_addr, data, on_sent,
                                *args, **kwargs)

    # client or server use
    def send(self, remote_addr, data):
        self.remote_addr = remote_addr
        try:
            self.sock.sendto(data, remote_addr)
            if not self.bind_addr:
                self.bind_addr = self.sock.getsockname()
            self.logger.debug("udp %s:%d sendto %s:%d, data len=%d",
                              self.bind_addr[0], self.bind_addr[1],
                              remote_addr[0], remote_addr[1],
                              len(data))
            cerr = ConnError(E_OK, "")
        except socket.error as err:
            self.logger.error("udp sendto %s:%d failed. error=%s",
                              self.bind_addr[0], self.bind_addr[1],
                              remote_addr[0], remote_addr[1], err)
            cerr = ConnError(E_FAIL, str(err))
        return cerr

    def __handle_asend(self, sock, remote_addr, data, on_sent,
                       *args, **kwargs):
        assert self.sock == sock
        self.io_engine.unregister(self.sock, ioloop.EV_WRITE)
        cerr = self.send(remote_addr, data)
        if on_sent:
            on_sent(self, remote_addr, cerr, *args, **kwargs)

    def arecv(self, on_recved, *args, **kwargs):
        self.io_engine.register(self.sock, ioloop.EV_READ,
                                self.__handle_arecv, on_recved,
                                *args, **kwargs)

    def __handle_arecv(self, sock, on_recved, *args, **kwargs):
        assert self.sock == sock
        cerr = None
        remote_addr = None
        data = None
        try:
            data, remote_addr = self.sock.recvfrom(self.recv_buffer_size)
            self.remote_addr = remote_addr
            self.logger.debug("udp %s:%d recvfrom %s:%d, data len=%d",
                              self.bind_addr[0], self.bind_addr[1],
                              remote_addr[0], remote_addr[1],
                              len(data))
            cerr = ConnError(E_OK, "")
        except socket.error as err:
            self.logger.error("udp %s:%d recvfrom failed. error=%s",
                              self.bind_addr[0], self.bind_addr[1], err)
            cerr = ConnError(E_FAIL, str(err))
        if on_recved:
            on_recved(self, remote_addr, data, cerr, *args, **kwargs)

class TCPConnection(Connection):
    def __init__(self, *args, **kwargs):
        super(TCPConnection, self).__init__(*args, **kwargs)
        self.sock = None
        self.sent = 0               # has sent data len
        self.send_data = b''        # data to send
        self.recved_buf = b''       # recved data buffer

    def set_keepalive(self):
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if sys.platform == 'linux':
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 2)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 2)

    def __close(self):
        self.io_engine.on_close_sock(self.sock)
        self.sock.close()
        self.closed = True

    def close(self):
        if not self.closed:
            self.__close()

    # server use
    def bind(self, bind_addr):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(bind_addr)
        except socket.error as err:
            self.logger.error("bind failed. error=%s", err)
            self.sock.close()
            raise BindException()
        self.bind_addr = self.sock.getsockname()
        self.logger.debug("bind to tcp %s:%d",
                          self.bind_addr[0], self.bind_addr[1])
        self.sock.listen(512)

    # server use
    def accept(self, on_connected, *args, **kwargs):
        self.io_engine.register(self.sock, ioloop.EV_READ,
                                self.__handle_accept, on_connected,
                                *args, **kwargs)

    # new connection
    def __handle_accept(self, sock, on_connected, *args, **kwargs):
        assert self.sock == sock
        newsock, remote_addr = self.sock.accept()
        self.logger.debug("tcp client %s:%d connected",
                          remote_addr[0], remote_addr[1])
        conn = TCPConnection(io_engine=self.io_engine)
        conn.bind_addr = newsock.getsockname()
        conn.remote_addr = remote_addr
        conn.sock = newsock
        conn.set_keepalive()
        if on_connected:
            on_connected(conn, ConnError(E_OK, ""), *args, **kwargs)

    # client use
    def aconnect(self, remote_addr, on_connected, *args, **kwargs):
        self.remote_addr = remote_addr
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(0)
        self.set_keepalive()
        try:
            self.sock.connect(self.remote_addr)
        except socket.error as err:
            if err.args[0] not in (errno.EINPROGRESS, errno.EWOULDBLOCK):
                self.logger.error("tcp connect to %s:%d failed. error=%s",
                                  self.remote_addr[0], self.remote_addr[1],
                                  err)
                self.__close()
                if on_connected:
                    on_connected(self, ConnError(E_FAIL, str(err)),
                                 *args, **kwargs)
                return
        self.bind_addr = self.sock.getsockname()
        self.io_engine.register(self.sock, ioloop.EV_READ|ioloop.EV_WRITE,
                                self.__handle_aconnect,
                                on_connected, *args, **kwargs)

    def __handle_aconnect(self, sock, on_connected, *args, **kwargs):
        assert self.sock == sock
        self.logger.debug("tcp %s:%d connected to %s:%d",
                          self.bind_addr[0], self.bind_addr[1],
                          self.remote_addr[0], self.remote_addr[1])
        self.io_engine.unregister(self.sock, ioloop.EV_READ|ioloop.EV_WRITE)
        if on_connected:
            on_connected(self, ConnError(E_OK, ""), *args, **kwargs)

    def asend(self, data, on_sent, *args, **kwargs):
        self.send_data = data
        self.io_engine.register(self.sock, ioloop.EV_WRITE,
                                self.__handle_asend,
                                on_sent, *args, **kwargs)

    def __handle_asend(self, sock, on_sent, *args, **kwargs):
        assert self.sock == sock
        cerr = None
        try:
            sent = self.sock.send(self.send_data[self.sent:])
            self.sent += sent
            if self.sent == len(self.send_data):
                self.io_engine.unregister(self.sock, ioloop.EV_WRITE)
                self.logger.debug("tcp %s:%d send to %s:%d data len %d",
                                  self.bind_addr[0], self.bind_addr[1],
                                  self.remote_addr[0], self.remote_addr[1],
                                  self.sent)
                self.sent = 0
                self.send_data = b''
                cerr = ConnError(E_OK, "")
            else:
                return
        except socket.error as err:
            if err.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                return
            self.logger.error("tcp %s:%d send to %s:%d failed. error=%s",
                              self.bind_addr[0], self.bind_addr[1],
                              self.remote_addr[0], self.remote_addr[1], err)
            self.__close()
            cerr = ConnError(E_FAIL, str(err))
        if on_sent:
            on_sent(self, cerr, *args, **kwargs)

    def arecv(self, want_byte, on_recved, *args, **kwargs):
        self.io_engine.register(self.sock, ioloop.EV_READ,
                                self.__handle_arecv, want_byte, on_recved,
                                *args, **kwargs)

    def __handle_arecv(self, sock, want_byte, on_recved, *args, **kwargs):
        assert self.sock == sock
        cerr = None
        try:
            data = self.sock.recv(want_byte - len(self.recved_buf))
            self.recved_buf += data
            if data:
                if len(self.recved_buf) < want_byte:
                    return
                self.logger.debug("tcp %s:%d recved from %s:%d data len %d",
                                  self.bind_addr[0], self.bind_addr[1],
                                  self.remote_addr[0], self.remote_addr[1],
                                  len(self.recved_buf))
                cerr = ConnError(E_OK, "")
            else:
                self.__close()
                cerr = ConnError(E_FAIL, "connection closed")
        except socket.error as err:
            if err.args[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                return
            self.logger.error("tcp %s:%d recv from %s:%d failed. error=%s",
                              self.bind_addr[0], self.bind_addr[1],
                              self.remote_addr[0], self.remote_addr[1], err)
            self.__close()
            cerr = ConnError(E_FAIL, str(err))
        if on_recved:
            on_recved(self, self.recved_buf, cerr, *args, **kwargs)
        self.recved_buf = b''
