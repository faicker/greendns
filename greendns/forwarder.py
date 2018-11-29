# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import socket
import time
import logging
from greendns import ioloop


class Forwarder(object):
    BUFSIZE = 2048

    def __init__(self, io_engine, upstreams, listen, timeout, handler):
        self.logger = logging.getLogger()
        self.upstreams = upstreams
        (ip, port) = listen.split(':')
        port = int(port)
        self.listen_addr = (ip, port)
        self.timeout = timeout
        self.sessions = {}      # sock -> Session
        self.io_engine = io_engine
        self.handler = handler
        self.s_sock = None
        self.s_sock = self.init_listen_sock(self.listen_addr)

    def init_listen_sock(self, listen_addr):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
            self.logger.error("sendto %s:%d failed. error=%s",
                              client_addr[0], client_addr[1], e)
            return False
        self.logger.debug("sendto client %s:%d, data len=%d",
                          client_addr[0], client_addr[1], len(resp))
        return True

    def check_timeout(self):
        '''this is not accurate, max delay is 2 * timeout'''
        to_delete = []
        now = time.time()
        for sock, sess in self.sessions.items():
            if now < sess.send_ts + self.timeout:
                continue
            myaddr = sock.getsockname()
            self.logger.warning("%s:%d request to upstream timeout",
                              myaddr[0], myaddr[1])
            self.io_engine.unregister(sock)
            sock.close()
            self.logger.debug("closed sock %s:%d", myaddr[0], myaddr[1])
            to_delete.append(sock)
        for sock in to_delete:
            del self.sessions[sock]
            self.logger.debug("remaining request size=%d", len(self.sessions))

    def handle_response_from_upstream(self, sock):
        myaddr = sock.getsockname()
        sess = self.sessions.get(sock)
        if not sess:
            self.logger.warning("session %s:%d not found", myaddr[0], myaddr[1])
            return False

        if not sess.responsed:
            data = None
            resp = None
            try:
                data, remote_addr = sock.recvfrom(self.BUFSIZE)
                if data:
                    self.logger.debug("%s:%d recvfrom upstream %s:%d, data len=%d",
                                      myaddr[0], myaddr[1],
                                      remote_addr[0], remote_addr[1],
                                      len(data))
                    sess.server_resps[remote_addr] = data
                    resp = self.handler.on_upstream_response(sess, remote_addr)
                    if resp:
                        if self.send_response(sess.client_addr, resp):
                            sess.responsed = True
            except socket.error as e:
                self.logger.error("recvfrom failed. error=%s", e)

        self.io_engine.unregister(sock)
        sock.close()
        del self.sessions[sock]
        self.logger.debug("closed sock %s:%d", myaddr[0], myaddr[1])
        self.logger.debug("remaining request size=%d", len(self.sessions))
        return True

    def handle_request_from_client(self, s_sock):
        assert self.s_sock == s_sock
        data, remote_addr = self.s_sock.recvfrom(self.BUFSIZE)
        self.logger.debug("recvfrom client %s:%d, data len=%d",
                          remote_addr[0], remote_addr[1], len(data))
        if not data:
            return
        sess = self.handler.get_session()
        sess.client_addr = remote_addr
        sess.send_ts = time.time()
        sess.req_data = data
        is_continue, resp = self.handler.on_client_request(sess)
        if resp:
            self.send_response(sess.client_addr, resp)
            return
        if not is_continue:
            self.logger.error("invalid request from client")
            return
        for server_addr in self.upstreams:
            try:
                sock = None
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(data, server_addr)
            except socket.error as e:
                self.logger.error("sendto %s:%d failed. error=%s",
                                  server_addr[0], server_addr[1], e)
                if sock:
                    sock.close()
            else:
                myaddr = sock.getsockname()
                self.logger.debug("%s:%d sendto upstream %s:%d, data len=%d",
                                  myaddr[0], myaddr[1], server_addr[0],
                                  server_addr[1], len(data))
                self.io_engine.register(sock, ioloop.EV_READ,
                                        self.handle_response_from_upstream)
                self.sessions[sock] = sess

    def run_forever(self):
        self.io_engine.register(self.s_sock, ioloop.EV_READ,
                                self.handle_request_from_client)
        self.io_engine.add_timer(False, self.timeout, self.check_timeout)
        self.io_engine.run()
