# -*- coding: utf-8 -*-
from multiprocessing import Process
import socket
import random
import os
import signal
import time
import logging
import pytest
from six.moves import socketserver
from greendns.forwarder import Forwarder
from greendns.handler_quickest import QuickestHandler
from greendns import ioloop
from greendns.connection import Addr


logger = logging.getLogger()
ch = logging.StreamHandler()
logger.addHandler(ch)
logger.setLevel(logging.DEBUG)

class UdpEcho1Handler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        sock = self.request[1]
        time.sleep(0.3)
        sock.sendto(data * 2, self.client_address)


class TcpEchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        data = sock.recv(2048)
        sock.send(data)


@pytest.fixture
def udp_server_process():
    s1 = socketserver.UDPServer(
        ("127.0.0.1", random.randint(20000, 30000)),
        UdpEcho1Handler)
    server_addr1 = s1.server_address
    p1 = Process(target=s1.serve_forever)
    p1.start()

    s2 = socketserver.TCPServer(
        ("127.0.0.1", random.randint(20000, 30000)),
        TcpEchoHandler)
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
    addr1 = Addr("udp", *server_addr1)
    addr2 = Addr("tcp", *server_addr2)
    upstreams = [addr1, addr2]
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


def test_forwarder_ok(running_process):
    forwarder = running_process
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b"hello\n", forwarder.listen_addr)
    time.sleep(0.5) # wait udp response
    data, _ = client.recvfrom(1024)
    client.close()
    assert data == b"hello\n"
    assert not forwarder.sessions


@pytest.fixture
def running_process_timeout(forwarder):
    forwarder.upstreams[0] = Addr("udp", "127.0.0.1", 1234)
    forwarder.upstreams[1] = Addr("tcp", "127.0.0.1", 1235)
    p = Process(target=forwarder.run_forever)
    p.start()
    yield forwarder
    os.kill(p.pid, signal.SIGINT)
    p.join()


def test_forwarder_timeout(running_process_timeout):
    forwarder = running_process_timeout
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b"hello\n", forwarder.listen_addr)
    client.settimeout(2)
    with pytest.raises(socket.timeout):
        client.recvfrom(1024)
    client.close()
    assert not forwarder.sessions
