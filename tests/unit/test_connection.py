# -*- coding: utf-8 -*-

import os
import signal
import time
import random
import socket
import logging
from multiprocessing import Process
import pytest
from six.moves import socketserver
from greendns import connection
from greendns import ioloop

logger = logging.getLogger()
ch = logging.StreamHandler()
logger.addHandler(ch)
logger.setLevel(logging.DEBUG)

# udp
class UdpEchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        sock = self.request[1]
        sock.sendto(data, self.client_address)


@pytest.fixture
def udp_server_process():
    s = socketserver.UDPServer(
        ("127.0.0.1", random.randint(20000, 30000)),
        UdpEchoHandler)
    server_addr = s.server_address
    p = Process(target=s.serve_forever)
    p.start()
    yield server_addr
    p.terminate()


def test_udp_client(udp_server_process):
    server_addr = udp_server_process
    io_engine = ioloop.get_ioloop("select")
    client = connection.UDPConnection(io_engine=io_engine)
    client.set_recv_buffer_size(2048)

    def on_recved(sock, _, data, err):
        client.close()
        client.stop()
        assert data == b'x' * 2048
        assert err.errcode == connection.E_OK

    def on_sent(sock, _, err):
        client.arecv(on_recved)
        assert err.errcode == connection.E_OK

    client.asend(server_addr, b'x' * 2048, on_sent)
    client.run()

@pytest.fixture
def my_udp_server():
    io_engine = ioloop.get_ioloop("select")
    server = connection.UDPConnection(io_engine=io_engine)
    server.bind(("127.0.0.1", 0))
    server.set_recv_buffer_size(2048)
    def on_sent(sock, _, err):
        server.close()
        server.stop()
        assert err.errcode == connection.E_OK
    def on_recved(sock, remote_addr, data, err):
        assert err.errcode == connection.E_OK
        server.asend(remote_addr, data, on_sent)

    server.arecv(on_recved)
    p = Process(target=server.run)
    p.start()
    yield server.bind_addr
    os.kill(p.pid, signal.SIGINT)
    p.join()

def test_udp_server(my_udp_server):
    server_addr = my_udp_server
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto( b'a' * 2000, server_addr)
    data, _ = sock.recvfrom(2048)
    sock.close()
    assert data == b'a' * 2000

def test_udp_bind(my_udp_server):
    server_addr = my_udp_server
    io_engine = ioloop.get_ioloop("select")
    server = connection.UDPConnection(io_engine=io_engine)
    with pytest.raises(connection.BindException):
        server.bind(server_addr)

# tcp
class TcpEchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        data = sock.recv(2048)
        time.sleep(0.3)
        sock.send(data)

@pytest.fixture
def tcp_server_process():
    server = socketserver.TCPServer(
        ("127.0.0.1", random.randint(20000, 30000)),
        TcpEchoHandler)
    server_addr = server.server_address
    pcs = Process(target=server.serve_forever)
    pcs.start()
    yield server_addr
    os.kill(pcs.pid, signal.SIGINT)
    pcs.join()

def test_tcp_client(tcp_server_process):
    server_addr = tcp_server_process
    io_engine = ioloop.get_ioloop("select")
    client = connection.TCPConnection(io_engine=io_engine)
    def on_recved(_, data, err):
        client.close()
        client.stop()
        assert data == b'x' * 2048
        assert err.errcode == connection.E_OK

    def on_sent(conn, err):
        assert err.errcode == connection.E_OK
        conn.arecv(2048, on_recved)

    def on_connected(conn, err):
        assert err.errcode == connection.E_OK
        conn.asend(b'x' * 2048, on_sent)
    client.aconnect(server_addr, on_connected)
    client.run()

def start_tcp_server():
    io_engine = ioloop.get_ioloop("select")
    server = connection.TCPConnection(io_engine=io_engine)
    server.bind(("127.0.0.1", random.randint(20000, 30000)))
    def on_sent(_, err):
        server.close()
        server.stop()
        assert err.errcode == connection.E_OK
    def on_recved(conn, data, err):
        assert err.errcode == connection.E_OK
        conn.asend(data, on_sent)
    def on_connected(newconn, err):
        assert err.errcode == connection.E_OK
        newconn.arecv(2000, on_recved)
    server.accept(on_connected)
    pcs = Process(target=server.run)
    pcs.start()
    return (server.bind_addr, pcs)

@pytest.fixture
def my_tcp_server():
    bind_addr, pcs = start_tcp_server()
    yield bind_addr
    os.kill(pcs.pid, signal.SIGINT)
    pcs.join()

def test_tcp_server():
    server_addr, pcs = start_tcp_server()
    time.sleep(1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(server_addr)
    sock.send(b'a' * 2000)
    data = sock.recv(2000)
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()
    os.kill(pcs.pid, signal.SIGINT)
    pcs.join()
    assert data == b'a' * 2000

def test_tcp_bind(my_tcp_server):
    server_addr = my_tcp_server
    time.sleep(1)
    io_engine = ioloop.get_ioloop("select")
    server = connection.TCPConnection(io_engine=io_engine)
    with pytest.raises(connection.BindException):
        server.bind(server_addr)

def test_aconnect_fail():
    server_addr = ("127.0.0.1234", 2)
    io_engine = ioloop.get_ioloop("select")
    client = connection.TCPConnection(io_engine=io_engine)
    def on_connected(_, err):
        client.stop()
        assert err.errcode == connection.E_FAIL
    client.aconnect(server_addr, on_connected)
    client.run()

def test_arecv_zero():
    server = socketserver.TCPServer(
        ("127.0.0.1", random.randint(20000, 30000)),
        TcpEchoHandler)
    server_addr = server.server_address
    pcs = Process(target=server.serve_forever)
    pcs.start()

    io_engine = ioloop.get_ioloop("select")
    client = connection.TCPConnection(io_engine=io_engine)
    def on_recved(_, data, err):
        client.close()
        client.stop()
        assert not data

    def on_sent(conn, err):
        assert err.errcode == connection.E_OK
        os.kill(pcs.pid, signal.SIGTERM)
        conn.arecv(2048, on_recved)
        pcs.join()

    def on_connected(conn, err):
        assert err.errcode == connection.E_OK
        conn.asend(b'x' * 2048, on_sent)
    time.sleep(1)
    client.aconnect(server_addr, on_connected)
    client.run()
