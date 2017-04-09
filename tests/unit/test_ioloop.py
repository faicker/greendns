# -*- coding: utf-8 -*-
import sys
import socket
from multiprocessing import Process, Pipe
import pytest
from six.moves import socketserver
from pychinadns import ioloop


server_addr = ("127.0.0.1", 42125)
if sys.platform == 'linux2':
    engines = ["select", "epoll"]
else:
    engines = ["select"]


class UdpEchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        sock = self.request[1]
        sock.sendto(data, self.client_address)


@pytest.fixture(params=engines)
def iol(request):
    return ioloop.get_ioloop(request.param)


@pytest.fixture(scope='class')
def udp_server_process():
    s = socketserver.UDPServer(server_addr, UdpEchoHandler, False)
    s.allow_reuse_address = True
    s.server_bind()
    s.server_activate()
    p = Process(target=s.serve_forever)
    p.start()
    yield p
    p.terminate()


class TestIOLoop:
    def test_register(self, iol):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        assert iol.register(sock, ioloop.EV_WRITE, self.write_func)
        assert not iol.rd_socks
        assert sock in iol.wr_socks
        assert iol.register(sock, ioloop.EV_READ, self.read_func)
        assert sock in iol.rd_socks
        sock.close()

    def test_unregister(self, iol):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        iol.register(sock, ioloop.EV_WRITE, self.write_func)
        assert iol.unregister(sock)
        iol.register(sock, ioloop.EV_READ|ioloop.EV_WRITE, self.read_func)
        assert sock in iol.rd_socks
        assert sock in iol.wr_socks
        assert iol.unregister(sock, ioloop.EV_READ)
        assert sock in iol.wr_socks
        sock.close()

    def test_run(self, iol, udp_server_process):
        parent_conn, child_conn = Pipe()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        iol.register(sock, ioloop.EV_WRITE, self.write_func, iol)
        iol.register(sock, ioloop.EV_READ, self.read_func, child_conn)
        p = Process(target=iol.run)
        p.start()
        assert parent_conn.recv()
        parent_conn.close()
        iol.unregister(sock)
        sock.close()
        p.terminate()

    def write_func(self, sock, iol):
        sock.sendto("hello\n", server_addr)
        iol.unregister(sock, ioloop.EV_WRITE)

    def read_func(self, sock, child_conn):
        (data, _) = sock.recvfrom(1024)
        assert data == "hello\n"
        child_conn.send(True)
        child_conn.close()
        sock.close()
