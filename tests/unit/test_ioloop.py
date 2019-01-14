# -*- coding: utf-8 -*-
import os
import signal
import sys
import socket
import random
from multiprocessing import Process, Pipe
import pytest
from six.moves import socketserver
from greendns import ioloop


if sys.platform.startswith('linux'):
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


@pytest.fixture
def udp_server_process():
    s = socketserver.UDPServer(
        ("127.0.0.1", random.randint(20000, 30000)),
        UdpEchoHandler)
    p = Process(target=s.serve_forever)
    p.start()
    yield s.server_address
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
        iol.register(sock, ioloop.EV_READ | ioloop.EV_WRITE, self.read_func)
        assert sock in iol.rd_socks
        assert sock in iol.wr_socks
        assert iol.unregister(sock, ioloop.EV_READ)
        assert sock in iol.wr_socks
        sock.close()

    def test_run(self, iol, udp_server_process):
        server_addr = udp_server_process
        print("server addr is %s:%d" %(server_addr[0], server_addr[1]))
        parent_conn, child_conn = Pipe()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        iol.register(sock, ioloop.EV_WRITE, self.write_func, iol, server_addr, child_conn)
        p = Process(target=iol.run)
        p.start()
        assert parent_conn.recv()
        parent_conn.close()
        sock.close()
        os.kill(p.pid, signal.SIGINT)
        p.join()

    def write_func(self, sock, iol, server_addr, child_conn):
        sock.sendto(b"hello\n", server_addr)
        iol.unregister(sock, ioloop.EV_WRITE)
        iol.register(sock, ioloop.EV_READ, self.read_func, child_conn, iol)

    def read_func(self, sock, child_conn, iol):
        (data, _) = sock.recvfrom(1024)
        assert data == b"hello\n"
        iol.on_close_sock(sock)
        sock.close()
        child_conn.send(True)
        child_conn.close()
