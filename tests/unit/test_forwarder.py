# -*- coding: utf-8 -*-
from multiprocessing import Process, Pipe
import socket
import pytest
import time
from six.moves import socketserver
from pychinadns.forwarder import Forwarder
from pychinadns.handler_quickest import QuickestHandler
from pychinadns import ioloop

server_addr1 = ("127.0.0.1", 42125)
server_addr2 = ("127.0.0.1", 42126)
forwarder_addr = ("127.0.0.1", 42053)


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
    s1 = socketserver.UDPServer(server_addr1, UdpEcho1Handler, False)
    s1.allow_reuse_address = True
    s1.server_bind()
    s1.server_activate()
    p1 = Process(target=s1.serve_forever)
    p1.start()
    s2 = socketserver.UDPServer(server_addr2, UdpEcho2Handler, False)
    s2.allow_reuse_address = True
    s2.server_bind()
    s2.server_activate()
    p2 = Process(target=s2.serve_forever)
    p2.start()
    yield (p1, p2)
    p1.terminate()
    p2.terminate()


@pytest.fixture
def forwarder():
    io_engine = ioloop.get_ioloop("select")
    upstreams = ",".join(["%s:%d" % (addr[0], addr[1]) for addr in (server_addr1, server_addr2)])
    listen = "%s:%d" % (forwarder_addr[0], forwarder_addr[1])
    timeout = 1.0
    handler = QuickestHandler()
    handler.init(io_engine)
    f = Forwarder(io_engine, upstreams, listen, timeout, handler)
    return f


@pytest.fixture
def running_process(forwarder):
    p = Process(target=forwarder.run_forever)
    p.start()
    yield p
    p.terminate()


def test_init_listen_sock(forwarder):
    sock = forwarder.init_listen_sock(("127.0.0.1", 0))
    assert sock
    sock.close()


def test_send_response(forwarder):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto("hello\n", forwarder_addr)
    data, client_addr = forwarder.s_sock.recvfrom(1024)
    forwarder.send_response(client_addr, data)
    data, _ = client.recvfrom(1024)
    client.close()
    assert data == "hello\n"


def test_handle_request_from_client(forwarder):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto("hello\n", forwarder_addr)
    forwarder.handle_request_from_client(forwarder.s_sock)
    client.close()
    assert len(forwarder.requests) == 2


def test_handle_response_from_upstream(forwarder, udp_server_process):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto("hello\n", forwarder_addr)
    forwarder.handle_request_from_client(forwarder.s_sock)
    time.sleep(0.2)
    for sock in forwarder.requests.keys():
        forwarder.handle_response_from_upstream(sock)
    assert len(forwarder.requests) == 0
    data, _ = client.recvfrom(1024)
    client.close()
    assert data in ["hello\n", "hello\nhello\n"]


def test_check_timeout(forwarder):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto("hello\n", forwarder_addr)
    forwarder.handle_request_from_client(forwarder.s_sock)
    assert len(forwarder.requests) == 2
    time.sleep(1)
    forwarder.check_timeout()
    client.close()
    assert len(forwarder.requests) == 0


def test_run_forever(running_process, udp_server_process):
    time.sleep(0.2)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto("hello\n", forwarder_addr)
    data, _ = client.recvfrom(1024)
    client.close()
    assert data in ["hello\n", "hello\nhello\n"]
