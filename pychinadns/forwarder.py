#!/usr/bin/env python
# coding=utf-8
import sys
import socket
import select
import time
import logging


class Request(object):
    def __init__(self):
        self.client_addr = ""     # client addr
        self.req_data = None      # client request
        self.send_ts = 0          # ts to send to upstream
        self.server_num = 0       # upstream server number
        self.server_conns = {}    # fileno -> sock
        self.server_resps = {}    # upstream server addr -> data
        self.resp_ts = {}         # upstream server addr -> ts


class Forwarder(object):
    BUFSIZE = 2048

    def __init__(self, upstreams, listen, timeout, response_handler):
        self.logger = logging.getLogger()
        self.upstreams = []
        for upstream in upstreams.split(','):
            (ip, port) = upstream.split(':')
            port = int(port)
            self.upstreams.append((ip, port))
        (ip, port) = listen.split(':')
        port = int(port)
        self.listen_addr = (ip, port)
        self.timeout = timeout
        self.epoll = None
        self.s_sock = None
        self.requests = {}
        self.response_handler = response_handler

    def init_sock(self):
        self.s_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s_sock.setblocking(0)
        try:
            self.s_sock.bind(self.listen_addr)
        except socket.error as e:
            self.logger.error("error to bind to %s:%d, %s"
                              % (self.listen_addr[0], self.listen_addr[1], e))
            sys.exit(1)

    def should_response(self, req):
        now = time.time()
        is_timeout = (now - req.send_ts >= self.timeout)
        if len(req.server_resps) == req.server_num or is_timeout:
            resp = self.response_handler(req)
            if resp:
                self.s_sock.sendto(resp, req.client_addr)
        self.logger.debug("fd %d sendto client %s:%d, data len=%d"
                          % (self.s_sock.fileno(),
                             req.client_addr[0], req.client_addr[1],
                             len(resp)))
        return is_timeout

    def handle_timeout(self):
        to_delete = []
        for fileno, req in self.requests.iteritems():
            is_timeout = self.should_response(req)
            if is_timeout:
                sock = req.server_conns[fileno]
                self.epoll.unregister(fileno)
                sock.close()
                to_delete.append(fileno)
        for fileno in to_delete:
            del self.requests[fileno]

    def run_forever(self):
        self.init_sock()
        self.epoll = select.epoll()
        self.epoll.register(self.s_sock.fileno(), select.EPOLLIN)
        while True:
            events = self.epoll.poll(1)
            # handle timeout
            self.handle_timeout()
            for fileno, event in events:
                if fileno in self.requests:
                    # response from upstream
                    req = self.requests[fileno]
                    if fileno in req.server_conns:
                        sock = req.server_conns[fileno]
                        data, remote_addr = sock.recvfrom(self.BUFSIZE)
                        self.epoll.unregister(fileno)
                        sock.close()
                        del self.requests[fileno]
                        self.logger.debug("requests size=%d" % (len(self.requests)))
                        if data:
                            self.logger.debug("fd %d recvfrom upstream %s:%d, data len=%d"
                                              % (fileno, remote_addr[0], remote_addr[1], len(data)))
                            req.server_resps[remote_addr] = data
                            req.resp_ts[remote_addr] = time.time()
                            self.should_response(req)
                elif fileno == self.s_sock.fileno():
                    # request from client
                    data, remote_addr = self.s_sock.recvfrom(self.BUFSIZE)
                    self.logger.debug("fd %d recvfrom client %s:%d, data len=%d"
                                      % (fileno, remote_addr[0], remote_addr[1], len(data)))
                    if data:
                        req = Request()
                        req.client_addr = remote_addr
                        req.send_ts = time.time()
                        req.server_num = len(self.upstreams)
                        req.req_data = data
                        for server_addr in self.upstreams:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            sock.setblocking(0)
                            sock.sendto(data, server_addr)
                            self.logger.debug("fd %d sendto upstream %s:%d, data len=%d"
                                              % (sock.fileno(), server_addr[0], server_addr[1], len(data)))
                            self.epoll.register(sock.fileno(), select.EPOLLIN)
                            req.server_conns[sock.fileno()] = sock
                            self.requests[sock.fileno()] = req
                else:
                    self.logger.error("can't find fileno %d" % (fileno))
                    continue
