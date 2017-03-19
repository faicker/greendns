#!/usr/bin/env python
# coding=utf-8
import sys
import socket
import time
import logging
import ioloop


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

    def __init__(self, upstreams, listen, timeout, mode, response_handler):
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
        self.s_sock = None
        self.requests = {}      # fileno -> Request
        self.response_handler = response_handler
        self.ioloop = ioloop.GetIOLoop(mode)

    def init_listen_sock(self):
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
                try:
                    self.s_sock.sendto(resp, req.client_addr)
                except socket.error as e:
                    self.logger.error("sendto %s:%d failed. error=%s"
                                      % (req.client_addr[0], req.client_addr[1], e))
                    return
                self.logger.debug("fd %d sendto client %s:%d, data len=%d"
                                  % (self.s_sock.fileno(),
                                     req.client_addr[0], req.client_addr[1],
                                     len(resp)))
        return is_timeout

    def check_timeout(self):
        to_delete = []
        for fileno, req in self.requests.iteritems():
            is_timeout = self.should_response(req)
            if is_timeout:
                self.logger.debug("request to upstream fd %d timeout"
                                  % (fileno))
                sock = req.server_conns[fileno]
                self.ioloop.Unregister(fileno)
                sock.close()
                to_delete.append(fileno)
        for fileno in to_delete:
            del self.requests[fileno]

    def handle_response_from_upstream(self, fileno):
        req = self.requests[fileno]
        if fileno in req.server_conns:
            sock = req.server_conns[fileno]
            data, remote_addr = sock.recvfrom(self.BUFSIZE)
            self.ioloop.Unregister(fileno)
            sock.close()
            del self.requests[fileno]
            self.logger.debug("requests size=%d" % (len(self.requests)))
            if data:
                self.logger.debug("fd %d recvfrom upstream %s:%d, data len=%d"
                                  % (fileno, remote_addr[0], remote_addr[1],
                                     len(data)))
                req.server_resps[remote_addr] = data
                req.resp_ts[remote_addr] = time.time()
                self.should_response(req)

    def handle_request_from_client(self, fileno):
        data, remote_addr = self.s_sock.recvfrom(self.BUFSIZE)
        self.logger.debug("fd %d recvfrom client %s:%d, data len=%d"
                          % (self.s_sock.fileno(),
                             remote_addr[0], remote_addr[1],
                             len(data)))
        if data:
            req = Request()
            req.client_addr = remote_addr
            req.send_ts = time.time()
            req.server_num = len(self.upstreams)
            req.req_data = data
            for server_addr in self.upstreams:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setblocking(0)
                    sock.sendto(data, server_addr)
                except socket.error as e:
                    self.logger.error("sendto %s:%d failed. error=%s"
                                      % (server_addr[0], server_addr[1], e))
                    sock.close()
                    continue
                self.logger.debug("fd %d sendto upstream %s:%d, data len=%d"
                                  % (sock.fileno(), server_addr[0],
                                     server_addr[1], len(data)))
                self.ioloop.Register(sock.fileno(), ioloop.EV_READ,
                                     self.handle_response_from_upstream)
                req.server_conns[sock.fileno()] = sock
                self.requests[sock.fileno()] = req

    def run_forever(self):
        self.init_listen_sock()
        self.ioloop.Register(self.s_sock.fileno(), ioloop.EV_READ,
                             self.handle_request_from_client)
        self.ioloop.AddTimer(self.timeout, self.check_timeout)
        self.ioloop.Run()
