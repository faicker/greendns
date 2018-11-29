# -*- coding: utf-8 -*-
from multiprocessing import Process
import socket
import os
import signal
import pytest
import time
from six.moves import socketserver
from greendns.forwarder import Forwarder
from greendns.handler_quickest import QuickestHandler
from greendns import ioloop


class UdpEcho1Handler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        sock = self.request[1]
        sock.sendto(data, self.client_address)


class UdpEcho2Handler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        sock = self.request[1]
        sock.sendto(data * 2, self.client_address)


@pytest.fixture
def udp_server_process():
    s1 = socketserver.UDPServer(("127.0.0.1", 0), UdpEcho1Handler)
    server_addr1 = s1.server_address
    p1 = Process(target=s1.serve_forever)
    p1.start()
    s2 = socketserver.UDPServer(("127.0.0.1", 0), UdpEcho2Handler)
    server_addr2 = s2.server_address
    p2 = Process(target=s2.serve_forever)
    p2.start()
    yield (server_addr1, server_addr2)
    p1.terminate()
    p2.terminate()


@pytest.fixture
def forwarder(udp_server_process):
    server_addr1, server_addr2 = udp_server_process
    io_engine = ioloop.get_ioloop("select")
    upstreams = [server_addr1, server_addr2]
    listen = "127.0.0.1:0"
    timeout = 1.0
    handler = QuickestHandler()
    handler.init(io_engine)
    f = Forwarder(io_engine, upstreams, listen, timeout, handler)
    return f


@pytest.fixture
def running_process(forwarder):
    p = Process(target=forwarder.run_forever)
    p.start()
    yield forwarder
    os.kill(p.pid, signal.SIGINT)
    p.join()


def test_init_listen_sock(forwarder):
    sock = forwarder.init_listen_sock(("127.0.0.1", 0))
    assert sock
    with pytest.raises(SystemExit):
        forwarder.init_listen_sock(forwarder.upstreams[0])
    sock.close()


def test_send_response(forwarder):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    forwarder_addr = forwarder.s_sock.getsockname()
    client.sendto(b"hello\n", forwarder_addr)
    data, client_addr = forwarder.s_sock.recvfrom(1024)
    assert forwarder.send_response(client_addr, data)
    data, _ = client.recvfrom(1024)
    client.close()
    assert data == b"hello\n"

    forwarder.s_sock.close()
    assert not forwarder.send_response(("127.0.0.1", 0), data)


def test_handle_request_from_client(forwarder):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    forwarder_addr = forwarder.s_sock.getsockname()
    client.sendto(b"hello\n", forwarder_addr)
    forwarder.handle_request_from_client(forwarder.s_sock)
    client.close()
    assert len(forwarder.sessions) == 2


def test_handle_response_from_upstream(forwarder):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    forwarder_addr = forwarder.s_sock.getsockname()
    client.sendto(b"hello\n", forwarder_addr)
    forwarder.handle_request_from_client(forwarder.s_sock)
    for sock in list(forwarder.sessions):
        ret = forwarder.handle_response_from_upstream(sock)
        assert ret
    ret = forwarder.handle_response_from_upstream(client) # no session
    assert not ret
    assert len(forwarder.sessions) == 0
    data, _ = client.recvfrom(1024)
    client.close()
    assert data in [b"hello\n", b"hello\nhello\n"]


def test_check_timeout(forwarder):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    forwarder_addr = forwarder.s_sock.getsockname()
    client.sendto(b"hello\n", forwarder_addr)
    forwarder.handle_request_from_client(forwarder.s_sock)
    assert len(forwarder.sessions) == 2
    time.sleep(1)
    forwarder.check_timeout()
    client.close()
    assert len(forwarder.sessions) == 0


def test_run_forever(running_process):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    forwarder = running_process
    forwarder_addr = forwarder.s_sock.getsockname()
    client.sendto(b"hello\n", forwarder_addr)
    data, _ = client.recvfrom(1024)
    client.close()
    assert data in [b"hello\n", b"hello\nhello\n"]
