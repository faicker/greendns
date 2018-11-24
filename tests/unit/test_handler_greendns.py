# -*- coding: utf-8 -*-
import os
import time
import argparse
import pytest
import dnslib
from greendns.handler_greendns import GreenDNSHandler
from greendns.handler_greendns import GreenDNSRequest

mydir = os.path.dirname(os.path.abspath(__file__))
local_dns1 = ("223.5.5.5", 53)
local_dns2 = ("1.2.4.8", 53)
foreign_dns = ("8.8.8.8", 53)


class IOEngineMock(object):
    def add_timer(*args, **kwargs):
        pass


def init_greendns_request(greendns, qname, qtype, id=1234):
    q = dnslib.DNSRecord.question(qname)
    q.header.id = id
    r = greendns.get_request()
    r.qname = qname
    r.qtype = qtype
    r.client_addr = ("127.0.0.1", 50453)
    r.send_ts = time.time()
    r.server_num = len(greendns.locals)
    r.req_data = bytes(q.pack())
    return r


@pytest.fixture
def greendns():
    h = GreenDNSHandler()
    parser = argparse.ArgumentParser()
    h.add_arg(parser)
    remaining_argv = ["-f", "%s/localroute_test.txt" % (mydir),
                      "-b", "%s/iplist_test.txt" % (mydir), "--cache"]
    h.parse_arg(parser, remaining_argv,
                "%s:%d,%s:%d" %
                (local_dns1[0], local_dns1[1],
                 foreign_dns[0], foreign_dns[1]))
    io_engine = IOEngineMock()
    h.init(io_engine)
    return h


def test_init():
    with pytest.raises(SystemExit):
        h = GreenDNSHandler()
        parser = argparse.ArgumentParser()
        h.add_arg(parser)
        remaining_argv = ["-f", "%s/localroute_test.txt" % (mydir),
                          "-b", "%s/iplist_test.txt" % (mydir), "--cache"]
        h.parse_arg(parser, remaining_argv,
                    "%s:%d,%s:%d" %
                    (local_dns1[0], local_dns1[1],
                     local_dns2[0], local_dns2[1]))
        io_engine = IOEngineMock()
        h.init(io_engine)


def test_get_request(greendns):
    r = greendns.get_request()
    assert isinstance(r, GreenDNSRequest)


def test_on_client_request_invalid(greendns):
    r = init_greendns_request(greendns, "google.com", dnslib.QTYPE.A)
    r.req_data = b'123456'
    is_continue, raw_resp = greendns.on_client_request(r)
    assert not is_continue
    assert not raw_resp


def test_on_client_request_without_cached(greendns):
    r = init_greendns_request(greendns, "google.com", dnslib.QTYPE.A)
    is_continue, raw_resp = greendns.on_client_request(r)
    assert is_continue
    assert not raw_resp


def test_on_client_request_with_cached(greendns):
    qname = "qq.com"
    id = 1024
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A, id)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("101.226.103.106"),
                                       ttl=3))
    greendns.cache.add(("qq.com.", 1), res, 3)
    is_continue, raw_resp = greendns.on_client_request(r)
    assert not is_continue
    assert raw_resp
    d = dnslib.DNSRecord.parse(raw_resp)
    assert d.header.id == id


def test_on_client_request_with_cache_expired(greendns):
    time.sleep(3)
    r = init_greendns_request(greendns, "qq.com", dnslib.QTYPE.A)
    is_continue, raw_resp = greendns.on_client_request(r)
    assert is_continue
    assert not raw_resp


def test_on_upstream_response_BD(greendns):
    qname = "google.com"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("1.2.3.4"),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("172.217.24.14")
    r.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "172.217.24.14"


def test_on_upstream_response_AD(greendns):
    qname = "www.microsoft.com"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("183.136.212.50"),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("184.85.123.14")
    r.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "183.136.212.50"


def test_on_upstream_response_AC(greendns):
    qname = "www.coding.net"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("219.146.244.91"),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("120.132.59.101")
    r.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "219.146.244.91"


def test_on_upstream_response_BC(greendns):
    qname = "www.x.net"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("8.8.8.8"),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("1.2.4.8")
    r.server_resps[foreign_dns] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "1.2.4.8"


def test_on_upstream_response_invalid_A(greendns):
    qname = "www.x.net"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("1.2.4.8"),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    r.server_resps[foreign_dns] = b'123456'
    resp = greendns.on_upstream_response(r)
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "1.2.4.8"


def test_on_upstream_response_not_A(greendns):
    qname = "www.microsoft.com"
    qresult = "www.microsoft.com-c-2.edgekey.net."
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.CNAME)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rtype=dnslib.QTYPE.CNAME,
                                       rdata=dnslib.CNAME(qresult),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    resp = greendns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == qresult


def test_on_upstream_response_invalid_not_A(greendns):
    qname = "www.x.net"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.CNAME)
    r.server_resps[local_dns1] = b'123456'
    resp = greendns.on_upstream_response(r)
    assert not resp


def test_on_timeout_with_notimeout(greendns):
    qname = "www.x.net"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    time.sleep(1)
    is_timeout, resp = greendns.on_timeout(r, 3)
    assert not is_timeout
    assert not resp


def test_on_timeout_with_none_response(greendns):
    qname = "www.x.net"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    time.sleep(1)
    is_timeout, resp = greendns.on_timeout(r, 1)
    assert is_timeout
    assert not resp


def test_on_timeout_with_one_response_ok(greendns):
    qname = "www.qq.com"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("101.226.103.106"),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    time.sleep(1)
    is_timeout, resp = greendns.on_timeout(r, 1)
    assert is_timeout
    assert resp


def test_on_timeout_with_one_response_invalid(greendns):
    qname = "www.qq.com"
    r = init_greendns_request(greendns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("8.8.8.8"),
                                       ttl=3))
    r.server_resps[local_dns1] = bytes(res.pack())
    time.sleep(1)
    is_timeout, resp = greendns.on_timeout(r, 1)
    assert is_timeout
    assert not resp
