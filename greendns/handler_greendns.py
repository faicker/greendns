# -*- coding: utf-8 -*-
from __future__ import print_function
import logging
import time
import argparse
import dnslib
from greendns import session
from greendns import localnet
from greendns import handler_base
from greendns import cache


class GreenDNSSession(session.Session):
    def __init__(self):
        super(GreenDNSSession, self).__init__()
        self.qtype = 0
        self.qname = ""
        self.is_poisoned = False
        self.local_result = None
        self.unpoisoned_result = None
        self.matrix = [[0, 0], [0, 0]]


class GreenDNSHandler(handler_base.HandlerBase):
    '''
    First filter poisoned ip with blocked iplist with -b argument.
    Second,
                                           | A record is local | A record is foreign
        local and poisoned dns server      |    a              |   b
        unpoisoned dns server              |    c              |   d

    From the matrix, we get the result as follows,
    ac: use local dns server result
    ad: use local dns server result
    bc: impossible. use unpoisoned dns server result
    bd: use unpoisoned dns server result
    '''
    def __init__(self):
        self.logger = logging.getLogger()
        self.cnet = None
        self.f_localroute = None
        self.f_blacklist = None
        self.using_rfc1918 = None
        self.lds = None
        self.rds = None
        self.cache_enabled = False
        self.cache = cache.Cache()
        self.local_servers = []
        self.unpoisoned_servers = []

    def add_arg(self, parser):
        parser.add_argument("--lds",
                            help="Specify local poisoned dns servers",
                            default="223.6.6.6:53,114.114.114.114:53")
        parser.add_argument("--rds",
                            help="Specify unpoisoned dns servers",
                            default="208.67.222.220:443,193.112.15.186:2323")
        parser.add_argument("-f", "--localroute", dest="localroute",
                            type=argparse.FileType('r'), required=True,
                            help="Specify local routes file")
        parser.add_argument("-b", "--blacklist", dest="blacklist",
                            type=argparse.FileType('r'), required=True,
                            help="Specify ip blacklist file")
        parser.add_argument("--rfc1918", dest="rfc1918", action="store_true",
                            help="Specify if rfc1918 ip is local")
        parser.add_argument("--cache", dest="cache", action="store_true",
                            help="Specify if cache is enabled")

    def parse_arg(self, parser, remaining_argv):
        myargs = parser.parse_args(remaining_argv)
        self.f_localroute = myargs.localroute
        self.f_blacklist = myargs.blacklist
        self.using_rfc1918 = myargs.rfc1918
        self.cache_enabled = myargs.cache
        self.lds = myargs.lds
        self.rds = myargs.rds

    def init(self, io_engine):
        self.cnet = localnet.LocalNet(self.f_localroute,
                                      self.f_blacklist,
                                      self.using_rfc1918)
        for l in self.lds.split(','):
            self.local_servers.append(self.parse_addr(l))
        for r in self.rds.split(','):
            self.unpoisoned_servers.append(self.parse_addr(r))

        if self.cache_enabled:
            io_engine.add_timer(False, 1, self.__decrease_ttl_one)

        return self.local_servers + self.unpoisoned_servers

    def get_session(self):
        return GreenDNSSession()

    def on_client_request(self, sess):
        is_continue, raw_resp = False, ""
        try:
            d = dnslib.DNSRecord.parse(sess.req_data)
        except Exception as e:
            self.logger.error("parse request error, msg=%s, data=%s",
                              e, sess.req_data)
            return (is_continue, raw_resp)
        self.logger.debug("request detail,\n%s", d)
        if len(d.questions) == 0:
            return (is_continue, raw_resp)
        qtype = d.questions[0].qtype
        qname = str(d.questions[0].qname)
        tid = d.header.id
        self.logger.info("received request, name=%s, type=%s, id=%d",
                         qname, dnslib.QTYPE.get(qtype), tid)
        if self.cache_enabled:
            resp = self.cache.find((qname, qtype))
            if resp:
                self.__replace_id(resp, tid)
                self.logger.info("cache hit")
                self.logger.debug("response detail,\n%s", resp)
                return (is_continue, bytes(resp.pack()))
        sess.qtype, sess.qname = qtype, qname
        is_continue = True
        return (is_continue, raw_resp)

    def on_upstream_response(self, sess, addr):
        if sess.qtype == dnslib.QTYPE.A:
            return self.__handle(sess, addr)
        else:
            #using the first answer from local server
            if addr in self.local_servers:
                return self.__handle(sess, addr)
            return ""

    def __handle(self, sess, addr):
        if sess.qtype == dnslib.QTYPE.A:
            resp = self.__handle_A(sess, addr)
        else:
            resp = self.__handle_other(sess, addr)
        if resp:
            if self.cache_enabled and resp.rr:
                for answer in resp.rr:
                    if answer.rtype == sess.qtype:
                        ttl = answer.ttl
                        self.cache.add((sess.qname, sess.qtype), resp, ttl)
                        self.logger.info(
                            "add to cache, key=(%s, %s), ttl=%d",
                            sess.qname, dnslib.QTYPE.get(sess.qtype), ttl)
                        break
            return bytes(resp.pack())
        return ""

    def __handle_other(self, sess, addr):
        data = sess.server_resps.get(addr)
        if not data:
            return None
        try:
            d = dnslib.DNSRecord.parse(data)
            self.logger.debug("%s:%d response detail,\n%s", addr[0], addr[1], d)
            return d
        except Exception as e:
            self.logger.error("parse response error, msg=%s, data=%s",
                              e, data)
            return None

    def __handle_A(self, sess, addr):
        data = sess.server_resps.get(addr)
        if not data:
            return None
        try:
            d = dnslib.DNSRecord.parse(data)
        except Exception as e:
            self.logger.error("parse response error, err=%s, data=%s",
                              e, data)
            return None
        str_ip = self.__parse_A(d)
        self.logger.info("%s:%d answered ip=%s", addr[0], addr[1], str_ip)
        self.logger.debug("%s:%d response detail,\n%s", addr[0], addr[1], d)
        if self.cnet.is_in_blacklist(str_ip):
            self.logger.info("ip %s is in blacklist", str_ip)
            sess.is_poisoned = True
            return None
        if addr in self.local_servers:
            if sess.local_result:
                return None
            sess.local_result = d
            if str_ip:
                if self.cnet.is_in_local(str_ip):
                    sess.matrix[0][0] = 1
                    self.logger.info(
                        "local server %s:%d returned local addr %s",
                        addr[0], addr[1], str_ip)
                else:
                    sess.matrix[0][1] = 1
                    self.logger.info(
                        "local server %s:%d returned foreign addr %s",
                        addr[0], addr[1], str_ip)
        elif addr in self.unpoisoned_servers:
            if sess.unpoisoned_result:
                return None
            sess.unpoisoned_result = d
        else:
            self.logger.warning("unexpected answer from unknown server")
            return None
        return self.__make_response(sess.local_result,
                                    sess.unpoisoned_result,
                                    sess.matrix,
                                    sess.is_poisoned)

    def __make_response(self, local_result, unpoisoned_result, m, is_poisoned):
        # calculate
        resp = None
        if m[0][0]:
            resp = local_result
        elif m[0][1] or is_poisoned:
            resp = unpoisoned_result
        elif local_result:
            # empty body, no IP
            resp = unpoisoned_result
        # log
        if resp:
            if resp == local_result:
                self.logger.info("using local result")
            else:
                self.logger.info("using unpoisoned result")
        return resp

    def __parse_A(self, record):
        '''parse a proper A record'''
        str_ip = ""
        local_ip = ""
        for rr in record.rr:
            if rr.rtype == dnslib.QTYPE.A:
                str_ip = str(rr.rdata)
                if self.cnet.is_in_local(str_ip):
                    local_ip = str_ip
        if local_ip:
            return local_ip
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
