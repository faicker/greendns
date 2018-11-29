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
from greendns import greendns
from greendns.handler_greendns import GreenDNSHandler


def get_myip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    myip = s.getsockname()[0]
    s.close()
    return myip


myip = get_myip()
qname = "www.qq.com"
mydir = os.path.dirname(os.path.abspath(__file__))


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
        time.sleep(0.3)
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
    return greendns.GreenDNS()


def test_check_loglevel():
    for k, v in greendns.str2level.items():
        assert k == greendns.check_loglevel(k)
    with pytest.raises(argparse.ArgumentTypeError):
        greendns.check_loglevel("undefined")


def test_load_mod():
    mod = greendns.load_mod("greendns", "handler_base")
    assert mod is not None
    mod = greendns.load_mod("greendns", "notexist")
    assert mod is None


def test_check_handler():
    obj = greendns.check_handler("greendns")
    assert obj is not None
    with pytest.raises(SystemExit):
        greendns.check_handler("notexist")


def test_setup_logger(dns):
    dns.setup_logger(loglevel="debug")
    import logging
    logger = logging.getLogger()
    assert logger.level == logging.DEBUG


def test_parse_config(dns):
    dns.parse_config(["-p", "127.0.0.1:42153", "-r", "greendns",
                      "-l", "debug",
                      "-f", "%s/localroute_test.txt" % (mydir),
                      "-b", "%s/iplist_test.txt" % (mydir),
                      "--lds", "127.0.0.1:42125",
                      "--rds", "127.0.0.2:42126",
                      "--cache"])
    assert dns.args.loglevel == "debug"
    assert dns.args.mode == "select"
    assert dns.args.listen == "127.0.0.1:42153"
    assert isinstance(dns.args.handler, GreenDNSHandler)


def test_parse_config_without_listen_ip(dns):
    dns.parse_config(["-p", "42153", "-r", "greendns",
                      "-l", "debug",
                      "-f", "%s/localroute_test.txt" % (mydir),
                      "-b", "%s/iplist_test.txt" % (mydir),
                      "--lds", "127.0.0.1:42125",
                      "--rds", "127.0.0.2:42126",
                      "--cache"])
    assert dns.args.listen == "127.0.0.1:42153"


def test_parse_config_help(dns):
    with pytest.raises(SystemExit):
        dns.parse_config([""])

    with pytest.raises(SystemExit):
        dns.parse_config(["-h"])

    with pytest.raises(SystemExit):
        dns.parse_config(["-r", "greendns", "-h"])


def test_run_forwarder(dns, udp_server_process):
    addr1, addr2 = udp_server_process
    dns.parse_config(["-p", "127.0.0.1:0",
                      "-r", "greendns",
                      "-l", "debug",
                      "-f", "%s/localroute_test.txt" % (mydir),
                      "-b", "%s/iplist_test.txt" % (mydir),
                      "--lds", "%s:%d" % (addr1[0], addr1[1]),
                      "--rds", "%s:%d" % (addr2[0], addr2[1]),
                      "--cache"])
    dns.setup_logger()
    dns.init_forwarder()
    forward_addr = dns.forwarder.s_sock.getsockname()
    p = Process(target=dns.run_forwarder)
    p.start()
    time.sleep(0.5)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    q = dnslib.DNSRecord.question(qname)
    client.sendto(bytes(q.pack()), forward_addr)
    time.sleep(0.5)
    data, _ = client.recvfrom(1024)
    d = dnslib.DNSRecord.parse(data)
    assert str(d.rr[0].rdata) == "101.226.103.106"
    assert d.rr[0].ttl == 3
    time.sleep(1.0)
    client.sendto(bytes(q.pack()), forward_addr)
    time.sleep(0.5)
    data, _ = client.recvfrom(1024)
    d = dnslib.DNSRecord.parse(data)
    assert str(d.rr[0].rdata) == "101.226.103.106"
    assert d.rr[0].ttl == 2
    client.close()
    os.kill(p.pid, signal.SIGINT)
    p.join()


def test_run_with_greendns_handler(udp_server_process):
    addr1, addr2 = udp_server_process
    forward_addr = ("127.0.0.1", 42353)
    argv = ["-p", "%s:%d" % (forward_addr[0], forward_addr[1]),
            "-r", "greendns",
            "-l", "debug",
            "-f", "%s/localroute_test.txt" % (mydir),
            "-b", "%s/iplist_test.txt" % (mydir),
            "--lds", "%s:%d" % (addr1[0], addr1[1]),
            "--rds", "%s:%d" % (addr2[0], addr2[1]),
            "--cache"]
    p = Process(target=greendns.run, args=(argv,))
    p.start()
    time.sleep(0.5)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    q = dnslib.DNSRecord.question(qname)
    client.sendto(bytes(q.pack()), forward_addr)
    time.sleep(0.5)
    data, _ = client.recvfrom(1024)
    d = dnslib.DNSRecord.parse(data)
    assert str(d.rr[0].rdata) == "101.226.103.106"
    client.close()
    os.kill(p.pid, signal.SIGINT)
    p.join()

def test_run_with_quickest_handler(udp_server_process):
    addr1, addr2 = udp_server_process
    forward_addr = ("127.0.0.1", 42354)
    argv = ["-p", "%s:%d" % (forward_addr[0], forward_addr[1]),
            "-r", "quickest",
            "-l", "debug",
            "--upstreams",
                "%s:%d,%s:%d" % (addr1[0], addr1[1], addr2[0], addr2[1])]
    p = Process(target=greendns.run, args=(argv,))
    p.start()
    time.sleep(0.5)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    q = dnslib.DNSRecord.question(qname)
    client.sendto(bytes(q.pack()), forward_addr)
    time.sleep(0.5)
    data, _ = client.recvfrom(1024)
    d = dnslib.DNSRecord.parse(data)
    assert str(d.rr[0].rdata) == "101.226.103.106"
    client.close()
    os.kill(p.pid, signal.SIGINT)
    p.join()
