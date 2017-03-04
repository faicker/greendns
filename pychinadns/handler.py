#!/usr/bin/env python
# coding=utf-8
from __future__ import print_function
import sys
import logging
import struct
import socket
import argparse
import dnslib

class QuickestResponseHandler(object):
    def __init__(self):
        pass
    def add_arg(self, parser):
        pass
    def init(self, args):
        pass
    def __call__(self, req):
        resp = ""
        if req.server_num > 0:
            least_ts = sys.maxint
            least_upstream = None
            for upstream, ts in req.resp_ts.iteritems():
                if ts < least_ts:
                    least_ts = ts
                    least_upstream = upstream
            resp = req.server_resps[least_upstream]
        return resp

class ChinaDNSReponseHandler(object):
    '''
        First filter poisoned ip with block iplist.
        Second,
                                   | result is local | result is foreign
             local dns server      |    A            |   B
             foreign dns server    |    C            |   D

        AC: use local dns server result
        AD: use local dns server result
        BC: not possible. use foreign dns server result
        BD: use foreign dns server result

    '''
    def __init__(self):
        self.china_subs = []
        self.blackips = set()
        self.logger = logging.getLogger()
        self.locals = {}                    # big-endian ip -> is_local(True/False)

    def add_arg(self, parser):
        parser.add_argument("-f", "--chnroute", dest="chnroute",
                            type=argparse.FileType('r'), required=True,
                            help="Specify chnroute file")
        parser.add_argument("--rfc1918", dest="rfc1918", action="store_true",
                            help="Specify if rfc1918 ip is local")
        parser.add_argument("-b", "--blacklist", dest="blacklist",
                            type=argparse.FileType('r'), required=True,
                            help="Specify ip blacklist file")

    def _convert(self, net):
        (ip_s, mask_s) = net.split('/')
        if ip_s and mask_s:
            try:
                ip = struct.unpack('>I', socket.inet_aton(ip_s))[0]
            except socket.error as e:
                return ()
            mask = int(mask_s)
            if mask < 0 and mask > 32:
                return ()
            hex_mask = 0xffffffff - (1 << (32 - mask)) + 1
            lowest = ip & hex_mask
            highest = lowest + (1 << (32 - mask)) - 1
            return (lowest, highest)

    def init(self, args):
        for sub in args.chnroute:
            (l, h) = self._convert(sub)
            if l and h:
                self.china_subs.append((l, h))
        for ip in args.blacklist:
            self.blackips.add(struct.unpack('>I', socket.inet_aton(ip))[0])
        if args.rfc1918:
            self.china_subs.append(self._convert("192.168.0.0/16"))
            self.china_subs.append(self._convert("10.0.0.0/8"))
            self.china_subs.append(self._convert("172.16.0.0/12"))
        self.china_subs.sort()

        i, j = 0, 0
        for upstream in args.upstream.split(','):
            ip, port = upstream.split(':')
            upstream_ip = struct.unpack('>I', socket.inet_aton(ip))[0]
            if self._is_in_china(upstream_ip):
                self.locals[upstream_ip] = True
                i += 1
            else:
                self.locals[upstream_ip] = False
                j += 1
        if i == 0 or j == 0:
            print("%s are invalid upstreams, at lease one local and one foreign" % args.upstream, file=sys.stderr)
            sys.exit(1)

    def _is_in_china(self, ip):
        '''binary search'''
        i = 0
        j = len(self.china_subs) - 1
        while (i <= j):
            k = (i + j) / 2
            if ip > self.china_subs[k][1]:
                i = k + 1
            elif ip < self.china_subs[k][0]:
                j = k - 1
            else:
                return True
        return False

    def __call__(self, req):
        quest_a = False
        try:
            d = dnslib.DNSRecord.parse(req.req_data)
        except Exception as e:
            self.logger.error("parse request error, msg=%s, data=%s" %(e, req.req_data))
            return ""
        self.logger.debug("request detail,\n%s" %(d))
        for quest in d.questions:
            if quest.qtype == dnslib.QTYPE.A:
                quest_a = True
            else:
                quest_a = False
        if quest_a:
            return self._handle_a(req)
        else:
            return self._handle_other(req)

    def _handle_other(self, req):
        resp = ""
        for upstream, data in req.server_resps.iteritems():
            resp = data
            ip, port = upstream
            upstream_ip = struct.unpack('>I', socket.inet_aton(ip))[0]
            if self.locals[upstream_ip]:
                return data
        return resp

    def _handle_a(self, req):
        resp = ""
        r = [[0, 0], [0, 0]]
        local_result = None
        foreign_result = None
        for upstream, data in req.server_resps.iteritems():
            ip, port = upstream
            upstream_ip = struct.unpack('>I', socket.inet_aton(ip))[0]
            try:
                d = dnslib.DNSRecord.parse(data)
            except Exception as e:
                self.logger.error("parse response error, msg=%s, data=%s" %(e, data))
                continue
            self.logger.debug("%s:%d response detail,\n%s" % (ip, port, d))
            for rr in d.rr:
                if rr.rtype == dnslib.QTYPE.A:
                    str_ip = str(rr.rdata)
                    dns_ip = struct.unpack('>I', socket.inet_aton(str_ip))[0]
                    if dns_ip in self.blackips:
                        break
                    if self.locals[upstream_ip]:
                        local_result = data
                        if self._is_in_china(dns_ip):
                            r[0][0] = 1
                            self.logger.info("local server %s:%d returned local addr %s" % (ip, port, str_ip))
                        else:
                            r[0][1] = 1
                            self.logger.info("local server %s:%d returned foreign addr %s" % (ip, port, str_ip))
                    else:
                        foreign_result = data
                        if not self._is_in_china(dns_ip):
                            r[1][0] = 1
                            self.logger.info("foregin server %s:%d returned foreign addr %s" % (ip, port, str_ip))
                        else:
                            r[1][1] = 1
                            self.logger.info("foregin server %s:%d returned local addr %s" % (ip, port, str_ip))
        if local_result and foreign_result:
            if r[0][0]:
                resp = local_result
            elif r[0][1]:
                resp = foreign_result
        else:
            self.logger.warning("only one server response")
            if local_result and r[0][0]:
                resp = local_result
            elif foreign_result:
                resp = foreign_result
        return resp
