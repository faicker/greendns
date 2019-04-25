# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import time
import logging
import struct
from greendns import connection


class Forwarder(object):
    def __init__(self, io_engine, upstreams, listen, timeout, handler):
        self.logger = logging.getLogger()
        self.io_engine = io_engine
        self.handler = handler
        self.upstreams = upstreams
        self.timeout = timeout
        # Connection -> Session, multi conn using the same Session object
        self.sessions = {}
        self.server = connection.UDPConnection(io_engine=self.io_engine)
        try:
            ip, port = listen.split(':')
            self.logger.info("binding to udp %s", listen)
            self.server.bind((ip, int(port)))
            self.listen_addr = self.server.bind_addr
        except connection.BindException:
            print("failed to bind to %s" % listen, file=sys.stderr)
            sys.exit(1)

    def send_response(self, client_addr, resp):
        self.server.send(client_addr, resp)

    def should_response(self, sess, addr):
        if not sess.responsed:
            resp = self.handler.on_upstream_response(sess, addr)
            if resp:
                self.send_response(sess.client_addr, resp)
                sess.responsed = True

    def check_timeout(self):
        '''this is not accurate, max delay is 2 * timeout'''
        to_delete = []
        now = time.time()
        for conn, sess in self.sessions.items():
            if now < sess.send_ts + self.timeout:
                continue
            if conn.bind_addr and conn.remote_addr:
                self.logger.warning("%s:%d request %s:%d to upstream timeout",
                                    conn.bind_addr[0], conn.bind_addr[1],
                                    conn.remote_addr[0], conn.remote_addr[1])
                conn.close()
            else:
                self.logger.warning("no bind addr")
            to_delete.append(conn)
        for conn in to_delete:
            del self.sessions[conn]
        if to_delete:
            self.logger.debug("remaining client request size=%d", len(self.sessions))

    def handle_request_from_client(self, conn, remote_addr, data, err):
        if err.errcode != connection.E_OK or not data:
            return
        sess = self.handler.new_session()
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
        for addr in self.upstreams:
            remote_addr = addr[1], addr[2]
            if addr.protocol == 'udp':
                conn = connection.UDPConnection(io_engine=self.io_engine)
                conn.asend(remote_addr, sess.req_data, self.handle_udp_request)
            elif addr.protocol == 'tcp':
                conn = connection.TCPConnection(io_engine=self.io_engine)
                conn.aconnect(remote_addr, self.handle_tcp_connected)
            else:
                self.logger.error("invalid protocol %s", addr.protocol)
                continue
            if conn:
                self.sessions[conn] = sess

    def handle_udp_request(self, conn, _, err):
        if err.errcode == connection.E_OK:
            conn.arecv(self.handle_udp_response)
        else:
            conn.close()
            del self.sessions[conn]

    def handle_udp_response(self, conn, remote_addr, data, err):
        sess = self.sessions.get(conn)
        assert sess
        conn.close()
        del self.sessions[conn]
        if err.errcode == connection.E_OK and data:
            self.logger.debug("remaining client request size=%d",
                              len(self.sessions))
            addr = connection.Addr('udp', remote_addr[0], remote_addr[1])
            sess.server_resps[addr] = data
            self.should_response(sess, addr)

    def handle_tcp_connected(self, conn, err):
        sess = self.sessions.get(conn)
        assert sess
        if err.errcode == connection.E_OK:
            data = struct.pack(">H%us" % len(sess.req_data),
                               len(sess.req_data), sess.req_data)
            conn.asend(data, self.handle_tcp_sent)
        else:
            conn.close()
            del self.sessions[conn]

    def handle_tcp_sent(self, conn, err):
        if err.errcode == connection.E_OK:
            payload_length_bytes = 2
            conn.arecv(payload_length_bytes, self.handle_length_recved)
        else:
            conn.close()
            del self.sessions[conn]

    def handle_length_recved(self, conn, data, err):
        if err.errcode == connection.E_OK:
            payload_length = struct.unpack(">H", data)[0]
            conn.arecv(payload_length, self.handle_payload_recved)
        else:
            conn.close()
            del self.sessions[conn]

    def handle_payload_recved(self, conn, data, err):
        sess = self.sessions.get(conn)
        assert sess
        conn.close()
        del self.sessions[conn]
        if err.errcode == connection.E_OK:
            self.logger.debug("remaining client request size=%d", len(self.sessions))
            addr = connection.Addr('tcp', conn.remote_addr[0], conn.remote_addr[1])
            sess.server_resps[addr] = data
            self.should_response(sess, addr)

    def run_forever(self):
        self.io_engine.add_timer(False, self.timeout, self.check_timeout)
        self.server.arecv(self.handle_request_from_client)
        self.logger.info("waiting for requests")
        self.server.run()
