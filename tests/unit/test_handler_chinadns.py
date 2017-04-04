# -*- coding: utf-8 -*-
import time
import argparse
import pytest
import dnslib
from pychinadns.handler_chinadns import ChinaDNSHandler
from pychinadns.handler_chinadns import ChinaDNSRequest


class IOEngineMock(object):
    def add_timer(*args, **kwargs):
        pass


def init_chinadns_request(chinadns, qname, qtype):
    q = dnslib.DNSRecord.question(qname)
    r = chinadns.get_request()
    r.qname = qname
    r.qtype = qtype
    r.client_addr = ("127.0.0.1", 50453)
    r.send_ts = time.time()
    r.server_num = len(chinadns.locals)
    r.req_data = str(q.pack())
    return r


@pytest.fixture
def chinadns():
    h = ChinaDNSHandler()
    parser = argparse.ArgumentParser()
    h.add_arg(parser)
    remaining_argv = ["-f", "etc/pychinadns/chnroute.txt",
                      "-b", "etc/pychinadns/iplist.txt", "--cache"]
    h.parse_arg(parser, remaining_argv, "223.5.5.5:53,127.0.0.1:5454")
    io_engine = IOEngineMock()
    h.init(io_engine)
    return h


def test_get_request(chinadns):
    r = chinadns.get_request()
    assert isinstance(r, ChinaDNSRequest)


def test_on_client_request_without_cached(chinadns):
    r = init_chinadns_request(chinadns, "google.com", dnslib.QTYPE.A)
    is_continue, raw_resp = chinadns.on_client_request(r)
    assert is_continue
    assert not raw_resp


def test_on_client_request_with_cached(chinadns):
    qname = "qq.com"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("101.226.103.106"),
                                       ttl=3))
    chinadns.cache.add(("qq.com.", 1), res, 3)
    is_continue, raw_resp = chinadns.on_client_request(r)
    assert not is_continue
    assert raw_resp


def test_on_client_request_with_cache_expired(chinadns):
    time.sleep(3)
    r = init_chinadns_request(chinadns, "qq.com", dnslib.QTYPE.A)
    is_continue, raw_resp = chinadns.on_client_request(r)
    assert is_continue
    assert not raw_resp


def test_on_upstream_response_BD(chinadns):
    qname = "google.com"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("216.58.200.46"),
                                       ttl=3))
    r.server_resps[("223.5.5.5", 53)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("172.217.24.14")
    r.server_resps[("127.0.0.1", 5454)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "172.217.24.14"


def test_on_upstream_response_AD(chinadns):
    qname = "www.microsoft.com"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("183.136.212.50"),
                                       ttl=3))
    r.server_resps[("223.5.5.5", 53)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("184.85.123.14")
    r.server_resps[("127.0.0.1", 5454)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "183.136.212.50"


def test_on_upstream_response_AC(chinadns):
    qname = "www.coding.net"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("219.146.244.91"),
                                       ttl=3))
    r.server_resps[("223.5.5.5", 53)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("120.132.59.101")
    r.server_resps[("127.0.0.1", 5454)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "219.146.244.91"


def test_on_upstream_response_BC(chinadns):
    qname = "www.x.net"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("8.8.8.8"),
                                       ttl=3))
    r.server_resps[("223.5.5.5", 53)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert not resp

    res.rr[0].rdata = dnslib.A("1.2.4.8")
    r.server_resps[("127.0.0.1", 5454)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == "1.2.4.8"


def test_on_upstream_response_not_A(chinadns):
    qname = "www.microsoft.com"
    qresult = "www.microsoft.com-c-2.edgekey.net."
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.CNAME)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rtype=dnslib.QTYPE.CNAME,
                                       rdata=dnslib.CNAME(qresult),
                                       ttl=3))
    r.server_resps[("223.5.5.5", 53)] = str(res.pack())
    resp = chinadns.on_upstream_response(r)
    assert resp
    d = dnslib.DNSRecord.parse(resp)
    assert str(d.rr[0].rdata) == qresult


def test_on_timeout_with_notimeout(chinadns):
    qname = "www.x.net"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    time.sleep(1)
    is_timeout, resp = chinadns.on_timeout(r, 3)
    assert not is_timeout
    assert not resp


def test_on_timeout_with_none_response(chinadns):
    qname = "www.x.net"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    time.sleep(1)
    is_timeout, resp = chinadns.on_timeout(r, 1)
    assert is_timeout
    assert not resp


def test_on_timeout_with_one_response(chinadns):
    qname = "www.qq.com"
    r = init_chinadns_request(chinadns, qname, dnslib.QTYPE.A)
    res = dnslib.DNSRecord(dnslib.DNSHeader(qr=1, aa=1, ra=1),
                           q=dnslib.DNSQuestion(qname),
                           a=dnslib.RR(qname,
                                       rdata=dnslib.A("101.226.103.106"),
                                       ttl=3))
    r.server_resps[("223.5.5.5", 53)] = str(res.pack())
    time.sleep(1)
    is_timeout, resp = chinadns.on_timeout(r, 1)
    assert is_timeout
    assert resp
