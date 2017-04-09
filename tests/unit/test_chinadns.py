# -*- coding: utf-8 -*-
import os
import signal
import time
from multiprocessing import Process
import socket
import argparse
import dnslib
import pytest
from six.moves import socketserver
from pychinadns import chinadns
from pychinadns.handler_chinadns import ChinaDNSHandler


def get_myip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    myip = s.getsockname()[0]
    s.close()
    return myip


myip = get_myip()
qname = "www.qq.com"


class UdpEcho1Handler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        d = dnslib.DNSRecord.parse(data)
        id = d.header.id
        sock = self.request[1]
        res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1, id=id),
                               q=dnslib.DNSQuestion(qname),
                               a=dnslib.RR(qname,
                                           rdata=dnslib.A("101.226.103.106"),
                                           ttl=3))
        sock.sendto(bytes(res.pack()), self.client_address)


class UdpEcho2Handler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        d = dnslib.DNSRecord.parse(data)
        id = d.header.id
        sock = self.request[1]
        res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1, id=id),
                               q=dnslib.DNSQuestion(qname),
                               a=dnslib.RR(qname,
                                           rdata=dnslib.A("182.254.8.146"),
                                           ttl=3))
        sock.sendto(bytes(res.pack()), self.client_address)


@pytest.fixture
def udp_server_process():
    s1 = socketserver.UDPServer(("127.0.0.1", 0), UdpEcho1Handler)
    server_addr1 = s1.server_address
    p1 = Process(target=s1.serve_forever)
    p1.start()
    s2 = socketserver.UDPServer((myip, 0), UdpEcho2Handler)
    server_addr2 = s2.server_address
    p2 = Process(target=s2.serve_forever)
    p2.start()
    yield (server_addr1, server_addr2)
    p1.terminate()
    p2.terminate()


@pytest.fixture
def dns():
    return chinadns.ChinaDNS()


def test_check_loglevel():
    for k, v in chinadns.str2level.items():
        assert k == chinadns.check_loglevel(k)
    with pytest.raises(argparse.ArgumentTypeError):
        chinadns.check_loglevel("undefined")


def test_load_mod():
    mod = chinadns.load_mod("pychinadns", "handler_base")
    assert mod is not None
    mod = chinadns.load_mod("pychinadns", "notexist")
    assert mod is None


def test_check_handler():
    obj = chinadns.check_handler("chinadns")
    assert obj is not None


def test_setup_logger(dns):
    dns.setup_logger()
    assert dns.logger


def test_parse_config1(dns):
    dns.parse_config(["-p", "127.0.0.1:42153", "-r", "chinadns",
                      "-u", "127.0.0.1:42125,127.0.0.2:42126", "-l", "debug",
                      "-f", "etc/pychinadns/chnroute.txt",
                      "-b", "etc/pychinadns/iplist.txt",
                      "--cache"])
    assert dns.args.loglevel == "debug"
    assert dns.args.mode == "select"
    assert dns.args.listen == "127.0.0.1:42153"
    assert isinstance(dns.args.handler, ChinaDNSHandler)


def test_parse_config2(dns):
    dns.parse_config(["-p", "42153", "-r", "chinadns",
                      "-u", "127.0.0.1:42125,127.0.0.2:42126", "-l", "debug",
                      "-f", "etc/pychinadns/chnroute.txt",
                      "-b", "etc/pychinadns/iplist.txt",
                      "--cache"])
    assert dns.args.listen == "127.0.0.1:42153"


def test_run_forwarder(dns, udp_server_process):
    addr1, addr2 = udp_server_process
    dns.parse_config(["-p", "127.0.0.1:0",
                      "-r", "chinadns",
                      "-u", "%s:%d,%s:%d" %
                      (addr1[0], addr1[1], addr2[0], addr2[1]),
                      "-l", "debug",
                      "-f", "tests/unit/chnroute_test.txt",
                      "-b", "etc/pychinadns/iplist.txt",
                      "--cache"])
    dns.setup_logger()
    dns.init_forwarder()
    forward_addr = dns.forwarder.s_sock.getsockname()
    p = Process(target=dns.run_forwarder)
    p.start()
    time.sleep(0.2)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    q = dnslib.DNSRecord.question(qname)
    client.sendto(bytes(q.pack()), forward_addr)
    data, _ = client.recvfrom(1024)
    d = dnslib.DNSRecord.parse(data)
    assert str(d.rr[0].rdata) == "101.226.103.106"
    assert d.rr[0].ttl == 3
    time.sleep(1.0)
    client.sendto(bytes(q.pack()), forward_addr)
    data, _ = client.recvfrom(1024)
    d = dnslib.DNSRecord.parse(data)
    assert str(d.rr[0].rdata) == "101.226.103.106"
    assert d.rr[0].ttl == 2
    client.close()
    os.kill(p.pid, signal.SIGINT)
    time.sleep(0.1)
    p.terminate()
