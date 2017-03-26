# -*- coding: utf-8 -*-


class Request(object):
    def __init__(self):
        self.client_addr = None   # client addr
        self.req_data = None      # client request
        self.send_ts = 0          # ts to send to upstream
        self.server_num = 0       # upstream server number
        self.server_conns = {}    # fileno -> sock
        self.server_resps = {}    # upstream server addr -> data
