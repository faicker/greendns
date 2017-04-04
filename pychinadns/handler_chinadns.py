# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import logging
import time
import argparse
import dnslib
from pychinadns import request
from pychinadns import chinanet
from pychinadns import handler_base
from pychinadns import cache


class ChinaDNSRequest(request.Request):
    def __init__(self):
        super(ChinaDNSRequest, self).__init__()
        self.qtype = 0
        self.qname = ""
        self.responsed = False


class ChinaDNSHandler(handler_base.HandlerBase):
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
        self.logger = logging.getLogger()
        self.cnet = None
        self.cache_enabled = False
        self.cache = cache.Cache()
        self.locals = {}          # str_ip -> is_local(True/False)

    def add_arg(self, parser):
        parser.add_argument("-f", "--chnroute", dest="chnroute",
                            type=argparse.FileType('r'), required=True,
                            help="Specify chnroute file")
        parser.add_argument("-b", "--blacklist", dest="blacklist",
                            type=argparse.FileType('r'), required=True,
                            help="Specify ip blacklist file")
        parser.add_argument("--rfc1918", dest="rfc1918", action="store_true",
                            help="Specify if rfc1918 ip is local")
        parser.add_argument("--cache", dest="cache", action="store_true",
                            help="Specify if cache is enabled")

    def parse_arg(self, parser, remaining_argv, s_upstream):
        myargs = parser.parse_args(remaining_argv)
        self.f_chnroute = myargs.chnroute
        self.f_blacklist = myargs.blacklist
        self.using_rfc1918 = myargs.rfc1918
        self.cache_enabled = myargs.cache
        self.s_upstream = s_upstream

    def init(self, io_engine):
        self.cnet = chinanet.ChinaNet(self.f_chnroute,
                                      self.f_blacklist,
                                      self.using_rfc1918)
        i, j = 0, 0
        for upstream in self.s_upstream.split(','):
            ip, port = upstream.split(':')
            if self.cnet.is_in_china(ip):
                self.locals[ip] = True
                i += 1
            else:
                self.locals[ip] = False
                j += 1
        if i == 0 or j == 0:
            print(
                "%s are invalid upstreams, "
                "at lease one local and one foreign"
                % (self.s_upstream),
                file=sys.stderr)
            sys.exit(1)

        if self.cache_enabled:
            io_engine.add_timer(False, 1, self.__decrease_ttl_one)

    def get_request(self):
        return ChinaDNSRequest()

    def on_client_request(self, req):
        is_continue, raw_resp = False, ""
        try:
            d = dnslib.DNSRecord.parse(req.req_data)
        except Exception as e:
            self.logger.error("parse request error, msg=%s, data=%s"
                              % (e, req.req_data))
            return (is_continue, raw_resp)
        self.logger.debug("request detail,\n%s" % (d))
        if len(d.questions) == 0:
            return (is_continue, raw_resp)
        qtype = d.questions[0].qtype
        qname = str(d.questions[0].qname)
        tid = d.header.id
        if self.cache_enabled:
            resp = self.cache.find((qname, qtype))
            if resp:
                self.__replace_id(resp, tid)
                self.logger.debug("cache hit, response detail,\n%s" % (resp))
                return (is_continue, bytes(resp.pack()))
        req.qtype = qtype
        req.qname = qname
        is_continue = True
        return (is_continue, raw_resp)

    def on_upstream_response(self, req):
        if (req.qtype == dnslib.QTYPE.A and
                len(req.server_resps) < req.server_num):
            return ""
        else:
            return self.__handle(req)

    def on_timeout(self, req, timeout):
        is_timeout, raw_resp = False, ""
        if time.time() >= req.send_ts + timeout:
            is_timeout = True
            raw_resp = self.__handle(req)
        return (is_timeout, raw_resp)

    def __handle(self, req):
        if req.responsed:
            return ""
        if req.qtype == dnslib.QTYPE.A:
            resp = self.__handle_A(req)
        else:
            resp = self.__handle_other(req)
        if resp:
            if self.cache_enabled and resp.rr:
                for answer in resp.rr:
                    if answer.rtype == req.qtype:
                        ttl = answer.ttl
                        self.cache.add((req.qname, req.qtype), resp, ttl)
                        self.logger.debug(
                            "add to cache, key=(%s, %d), ttl=%d"
                            % (req.qname, req.qtype, ttl))
                        break
            return bytes(resp.pack())
        else:
            return ""

    def __handle_other(self, req):
        for upstream, data in req.server_resps.items():
            ip, port = upstream
            try:
                d = dnslib.DNSRecord.parse(data)
                self.logger.debug("%s:%d response detail,\n%s" % (ip, port, d))
            except Exception as e:
                self.logger.error("parse response error, msg=%s, data=%s"
                                  % (e, data))
                return None
            req.responsed = True
            return d
        return None

    def __handle_A(self, req):
        r = [[0, 0], [0, 0]]
        resp = None
        local_result = None
        foreign_result = None
        for upstream, data in req.server_resps.items():
            ip, port = upstream
            try:
                d = dnslib.DNSRecord.parse(data)
            except Exception as e:
                self.logger.error("parse response error, msg=%s, data=%s"
                                  % (e, data))
                continue
            self.logger.debug("%s:%d response detail,\n%s" % (ip, port, d))
            if self.locals[ip]:
                str_ip = self.__parse_A(d)
                if self.cnet.is_in_blacklist(str_ip):
                    continue
                local_result = d
                if not str_ip:
                    continue
                if self.cnet.is_in_china(str_ip):
                    r[0][0] = 1
                    self.logger.info(
                        "local server %s:%d returned local addr %s"
                        % (ip, port, str_ip))
                else:
                    r[0][1] = 1
                    self.logger.info(
                        "local server %s:%d returned foreign addr %s"
                        % (ip, port, str_ip))
            else:
                str_ip = self.__parse_A(d)
                if self.cnet.is_in_blacklist(str_ip):
                    continue
                foreign_result = d
                if not str_ip:
                    continue
                if not self.cnet.is_in_china(str_ip):
                    r[1][0] = 1
                    self.logger.info(
                        "foregin server %s:%d returned foreign addr %s"
                        % (ip, port, str_ip))
                else:
                    r[1][1] = 1
                    self.logger.info(
                        "foregin server %s:%d returned local addr %s"
                        % (ip, port, str_ip))
        if local_result and foreign_result:
            if r[0][0]:
                resp = local_result
            else:
                resp = foreign_result
        elif local_result:
            if r[0][0] or (r[0][0] ^ r[0][1] == 0):
                resp = local_result
        elif foreign_result:
            resp = foreign_result
        return resp

    def __parse_A(self, record):
        '''parse first A record'''
        str_ip = ""
        for rr in record.rr:
            if rr.rtype == dnslib.QTYPE.A:
                str_ip = str(rr.rdata)
                break
        return str_ip

    def __replace_id(self, resp, new_tid):
        resp.header.id = new_tid
        return resp

    def __decrease_ttl_one(self):
        l = []
        for k, (v, _) in self.cache.iteritems():
            for rr in v.rr:
                rr.ttl -= 1
                if rr.ttl == 0:
                    l.append(k)
        for k in l:
            self.cache.remove(k)
