# -*- coding: utf-8 -*-
from __future__ import print_function
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
        self.requests = {}      # sock -> Request
        self.io_engine = io_engine
        self.handler = handler
        self.s_sock = self.init_listen_sock(self.listen_addr)

    def __del__(self):
        if self.s_sock:
            self.s_sock.close()
        for s in self.requests.keys():
            s.close()

    def init_listen_sock(self, listen_addr):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(0)
        try:
            sock.bind(listen_addr)
        except socket.error as e:
            print("error to bind to %s:%d, %s"
                              % (listen_addr[0], listen_addr[1], e), file=sys.stderr)
            sys.exit(1)
        else:
            return sock

    def send_response(self, client_addr, resp):
        try:
            self.s_sock.sendto(resp, client_addr)
        except socket.error as e:
            self.logger.error("sendto %s:%d failed. error=%s"
                              % (client_addr[0], client_addr[1], e))
            return
        self.logger.debug("sendto client %s:%d, data len=%d"
                          % (client_addr[0], client_addr[1], len(resp)))

    def check_timeout(self):
        to_delete = []
        for sock, req in self.requests.items():
            is_timeout, resp = self.handler.on_timeout(req, self.timeout)
            if resp:
                self.send_response(req.client_addr, resp)
            if is_timeout:
                myaddr = sock.getsockname()
                self.logger.debug("%s:%d request to upstream timeout"
                                  % (myaddr[0], myaddr[1]))
                self.io_engine.unregister(sock)
                sock.close()
                to_delete.append(sock)
        for sock in to_delete:
            del self.requests[sock]

    def handle_response_from_upstream(self, sock):
        req = self.requests.get(sock)
        if not req:
            return
        myaddr = sock.getsockname()
        data, remote_addr = sock.recvfrom(self.BUFSIZE)
        self.io_engine.unregister(sock)
        sock.close()
        del self.requests[sock]
        if data:
            self.logger.debug("%s:%d recvfrom upstream %s:%d, data len=%d"
                              % (myaddr[0], myaddr[1],
                                 remote_addr[0], remote_addr[1],
                                 len(data)))
            req.server_resps[remote_addr] = data
            resp = self.handler.on_upstream_response(req)
            if resp:
                self.send_response(req.client_addr, resp)
        self.logger.debug("upstream request size=%d" % (len(self.requests)))

    def handle_request_from_client(self, s_sock):
        assert self.s_sock == s_sock
        data, remote_addr = self.s_sock.recvfrom(self.BUFSIZE)
        self.logger.debug("recvfrom client %s:%d, data len=%d"
                          % (remote_addr[0], remote_addr[1], len(data)))
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
            else:
                myaddr = sock.getsockname()
                self.logger.debug("%s:%d sendto upstream %s:%d, data len=%d"
                                  % (myaddr[0], myaddr[1], server_addr[0],
                                     server_addr[1], len(data)))
                self.io_engine.register(sock, ioloop.EV_READ,
                                        self.handle_response_from_upstream)
                self.requests[sock] = req

    def run_forever(self):
        self.io_engine.register(self.s_sock, ioloop.EV_READ,
                                self.handle_request_from_client)
        self.io_engine.add_timer(False, self.timeout, self.check_timeout)
        self.io_engine.run()
