# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import logging
import argparse
import dnslib
import chinanet
import handler_base


class ChinaDNSReponseHandler(handler_base.HandlerBase):
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
        self.locals = {}          # str_ip -> is_local(True/False)

    def add_arg(self, parser):
        parser.add_argument("-f", "--chnroute", dest="chnroute",
                            type=argparse.FileType('r'), required=True,
                            help="Specify chnroute file")
        parser.add_argument("--rfc1918", dest="rfc1918", action="store_true",
                            help="Specify if rfc1918 ip is local")
        parser.add_argument("-b", "--blacklist", dest="blacklist",
                            type=argparse.FileType('r'), required=True,
                            help="Specify ip blacklist file")

    def init(self, s_upstream, f_chnroute, f_blacklist, using_rfc1918):
        self.cnet = chinanet.ChinaNet(f_chnroute,
                                      f_blacklist,
                                      using_rfc1918)
        i, j = 0, 0
        for upstream in s_upstream.split(','):
            ip, port = upstream.split(':')
            if self.cnet.is_in_china(ip):
                self.locals[ip] = True
                i += 1
            else:
                self.locals[ip] = False
                j += 1
        if i == 0 or j == 0:
            print("%s are invalid upstreams, at lease one local and one foreign"
                  % s_upstream, file=sys.stderr)
            sys.exit(1)

    def __call__(self, req):
        quest_A = False
        try:
            d = dnslib.DNSRecord.parse(req.req_data)
        except Exception as e:
            self.logger.error("parse request error, msg=%s, data=%s"
                              % (e, req.req_data))
            return ""
        self.logger.debug("request detail,\n%s" % (d))
        for quest in d.questions:
            if quest.qtype == dnslib.QTYPE.A:
                quest_A = True
            else:
                quest_A = False
        if quest_A:
            return self.__handle_A(req)
        else:
            return self.__handle_other(req)

    def __handle_other(self, req):
        resp = ""
        for upstream, data in req.server_resps.iteritems():
            resp = data
            ip, port = upstream
            if self.locals[ip]:
                return data
        return resp

    def __handle_A(self, req):
        resp = ""
        r = [[0, 0], [0, 0]]
        local_result = None
        foreign_result = None
        for upstream, data in req.server_resps.iteritems():
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
                local_result = data
                if not str_ip:
                    continue
                if self.cnet.is_in_china(str_ip):
                    r[0][0] = 1
                    self.logger.info("local server %s:%d returned local addr %s" % (ip, port, str_ip))
                else:
                    r[0][1] = 1
                    self.logger.info("local server %s:%d returned foreign addr %s" % (ip, port, str_ip))
            else:
                str_ip = self.__parse_A(d)
                if self.cnet.is_in_blacklist(str_ip):
                    continue
                foreign_result = data
                if not str_ip:
                    continue
                if not self.cnet.is_in_china(str_ip):
                    r[1][0] = 1
                    self.logger.info("foregin server %s:%d returned foreign addr %s" % (ip, port, str_ip))
                else:
                    r[1][1] = 1
                    self.logger.info("foregin server %s:%d returned local addr %s" % (ip, port, str_ip))
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
