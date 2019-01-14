# -*- coding: utf-8 -*-
import os
import time
import argparse
import pytest
import dnslib
from greendns.handler_greendns import GreenDNSHandler
from greendns.handler_greendns import GreenDNSSession
from greendns.connection import Addr

mydir = os.path.dirname(os.path.abspath(__file__))
local_dns1 = Addr("udp", "223.5.5.5", 53)
foreign_dns = Addr("udp", "8.8.8.8", 53)


class IOEngineMock(object):
    def add_timer(*args, **kwargs):
        pass


def init_greendns_session(greendns, qname, qtype, id=1234):
    q = dnslib.DNSRecord.question(qname)
    q.header.id = id
    s = greendns.new_session()
    s.qname = qname
    s.qtype = qtype
    s.client_addr = ("127.0.0.1", 50453)
    s.send_ts = time.time()
    s.req_data = bytes(q.pack())
    return s

def make_handler():
    h = GreenDNSHandler()
    parser = argparse.ArgumentParser()
    h.add_arg(parser)
    remaining_argv = ["-f", "%s/localroute_test.txt" % (mydir),
                      "-b", "%s/iplist_test.txt" % (mydir), "--cache",
                      "--lds", "%s:%d" % (local_dns1[1], local_dns1[2]),
                      "--rds",
                      "%s:%s:%d" %
                      (foreign_dns[0], foreign_dns[1], foreign_dns[2])]
    h.parse_arg(parser, remaining_argv)
    return h

@pytest.fixture
def greendns():
    h = make_handler()
    io_engine = IOEngineMock()
    h.init(io_engine)
    return h


def test_init():
    h = make_handler()
    io_engine = IOEngineMock()
    servers = h.init(io_engine)
    assert servers[0] == local_dns1
    assert servers[1] == foreign_dns


def test_new_session(greendns):
    s = greendns.new_session()
    assert isinstance(s, GreenDNSSession)


def test_on_client_request_invalid(greendns):
    s = init_greendns_session(greendns, "google.com", dnslib.QTYPE.A)
    s.req_data = b'123456'
    is_continue, raw_resp = greendns.on_client_request(s)
    assert not is_continue
    assert not raw_resp


def test_on_client_request_without_cached(greendns):
    s = init_greendns_session(greendns, "google.com", dnslib.QTYPE.A)
    is_continue, raw_resp = greendns.on_client_request(s)
    assert is_continue
    assert not raw_resp


def test_on_client_request_with_cached(greendns):
    qname = "qq.com"
    id = 1024
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A, id)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("101.226.103.106"),
                                       ttl=3))
    greendns.cache.add(("qq.com.", 1), res, 3)
    is_continue, raw_resp = greendns.on_client_request(s)
    assert not is_continue
    assert raw_resp
    d = dnslib.DNSRecord.parse(raw_resp)
    assert d.header.id == id


def test_on_client_request_with_cache_expired(greendns):
    qname = "qqq.com"
    id = 1024
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A, id)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("101.226.103.106"),
                                       ttl=3))
    greendns.cache.add(("qqq.com.", 1), res, 3)
    time.sleep(4)
    is_continue, raw_resp = greendns.on_client_request(s)
    assert is_continue
    assert not raw_resp


def test_on_upstream_response_BD(greendns):
    qname = "google.com"
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("1.2.3.4"),
                                       ttl=3))
    s.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, local_dns1)
    assert not resp

    res.rr[0].rdata = dnslib.A("172.217.24.14")
    s.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, foreign_dns)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "172.217.24.14"


def test_on_upstream_response_AD(greendns):
    qname = "www.microsoft.com"
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("184.85.123.14"),
                                       ttl=3))
    s.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, foreign_dns)
    assert not resp

    res.rr[0].rdata = dnslib.A("183.136.212.50")
    s.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, local_dns1)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "183.136.212.50"


def test_on_upstream_response_AC(greendns):
    qname = "www.coding.net"
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("120.132.59.101"),
                                       ttl=3))
    s.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, foreign_dns)
    assert not resp

    res.rr[0].rdata = dnslib.A("219.146.244.91")
    s.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, local_dns1)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "219.146.244.91"


def test_on_upstream_response_BC(greendns):
    qname = "www.x.net"
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("8.8.8.8"),
                                       ttl=3))
    s.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, local_dns1)
    assert not resp

    res.rr[0].rdata = dnslib.A("1.2.4.8")
    s.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, foreign_dns)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "1.2.4.8"


def test_on_upstream_response_invalid_A(greendns):
    qname = "www.x.net"
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("1.2.4.8"),
                                       ttl=3))
    s.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, local_dns1)
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "1.2.4.8"

    s.server_resps[local_dns1] = b'123456'
    resp = greendns.on_upstream_response(s, local_dns1)
    assert not resp


def test_on_upstream_response_not_A(greendns):
    qname = "www.microsoft.com"
    qresult = "www.microsoft.com-c-2.edgekey.net."
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.CNAME)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rtype=dnslib.QTYPE.CNAME,
                                       rdata=dnslib.CNAME(qresult),
                                       ttl=3))
    s.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(s, local_dns1)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == qresult


def test_on_upstream_response_invalid_not_A(greendns):
    qname = "www.x.net"
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.CNAME)
    s.server_resps[local_dns1] = b'123456'
    resp = greendns.on_upstream_response(s, local_dns1)
    assert not resp

def test_shuffer_A(greendns):
    qname = "qq.com"
    id = 1024
    s = init_greendns_session(greendns, qname, dnslib.QTYPE.A, id)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       dnslib.QTYPE.CNAME,
                                       rdata=dnslib.CNAME("https.qq.com"),
                                       ttl=3))
    res.add_answer(dnslib.RR(qname,
                             rdata=dnslib.A("101.226.103.106"),
                             ttl=3))
    res.add_answer(dnslib.RR(qname,
                             rdata=dnslib.A("101.226.103.107"),
                             ttl=3))
    greendns.cache.add(("qq.com.", 1), res, 3)
    d = None
    for i in range(10):
        is_continue, raw_resp = greendns.on_client_request(s)
        assert not is_continue
        assert raw_resp
        d = dnslib.DNSRecord.parse(raw_resp)
        if str(d.rr[1].rdata) == "101.226.103.107":
            break
    assert d.rr[0].rtype == dnslib.QTYPE.CNAME
    assert str(d.rr[1].rdata) == "101.226.103.107"
