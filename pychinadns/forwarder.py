# -*- coding: utf-8 -*-
import sys
import socket
import time
import logging
from pychinadns import ioloop


class Forwarder(object):
    BUFSIZE = 2048

    def __init__(self, io_engine, upstreams, listen, timeout, handler):
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
        self.io_engine = io_engine
        self.handler = handler

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

    def send_response(self, client_addr, resp):
        try:
            self.s_sock.sendto(resp, client_addr)
        except socket.error as e:
            self.logger.error("sendto %s:%d failed. error=%s"
                              % (client_addr[0], client_addr[1], e))
            return
        self.logger.debug("fd %d sendto client %s:%d, data len=%d"
                          % (self.s_sock.fileno(),
                             client_addr[0], client_addr[1],
                             len(resp)))

    def check_timeout(self):
        to_delete = []
        for fileno, req in self.requests.items():
            is_timeout, resp = self.handler.on_timeout(req, self.timeout)
            if resp:
                self.send_response(req.client_addr, resp)
            if is_timeout:
                self.logger.debug("request to upstream fd %d timeout"
                                  % (fileno))
                sock = req.server_conns[fileno]
                self.io_engine.unregister(fileno)
                sock.close()
                to_delete.append(fileno)
        for fileno in to_delete:
            del self.requests[fileno]

    def handle_response_from_upstream(self, fileno):
        req = self.requests[fileno]
        sock = req.server_conns.get(fileno)
        if not sock:
            return
        data, remote_addr = sock.recvfrom(self.BUFSIZE)
        self.io_engine.unregister(fileno)
        sock.close()
        del self.requests[fileno]
        if data:
            self.logger.debug("fd %d recvfrom upstream %s:%d, data len=%d"
                              % (fileno, remote_addr[0], remote_addr[1],
                                 len(data)))
            req.server_resps[remote_addr] = data
            resp = self.handler.on_upstream_response(req)
            if resp:
                self.send_response(req.client_addr, resp)
        self.logger.debug("upstream request size=%d" % (len(self.requests)))

    def handle_request_from_client(self, fileno):
        assert self.s_sock.fileno() == fileno
        data, remote_addr = self.s_sock.recvfrom(self.BUFSIZE)
        self.logger.debug("fd %d recvfrom client %s:%d, data len=%d"
                          % (self.s_sock.fileno(),
                             remote_addr[0], remote_addr[1],
                             len(data)))
        if len(data) == 0:
            return
        req = self.handler.get_request()
        req.client_addr = remote_addr
        req.send_ts = time.time()
        req.server_num = len(self.upstreams)
        req.req_data = data
        is_continue, resp = self.handler.on_client_request(req)
        if resp:
            self.send_response(req.client_addr, resp)
            return
        if not is_continue:
            self.logger.error("invalid request from client")
            return
        for server_addr in self.upstreams:
            try:
                sock = None
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setblocking(0)
                sock.sendto(data, server_addr)
            except socket.error as e:
                self.logger.error("sendto %s:%d failed. error=%s"
                                  % (server_addr[0], server_addr[1], e))
                if sock:
                    sock.close()
                continue
            self.logger.debug("fd %d sendto upstream %s:%d, data len=%d"
                              % (sock.fileno(), server_addr[0],
                                 server_addr[1], len(data)))
            self.io_engine.register(sock.fileno(), ioloop.EV_READ,
                                    self.handle_response_from_upstream)
            req.server_conns[sock.fileno()] = sock
            self.requests[sock.fileno()] = req

    def run_forever(self):
        self.init_listen_sock()
        self.io_engine.register(self.s_sock.fileno(), ioloop.EV_READ,
                                self.handle_request_from_client)
        self.io_engine.add_timer(False, self.timeout, self.check_timeout)
        self.io_engine.run()
