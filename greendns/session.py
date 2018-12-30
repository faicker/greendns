# -*- coding: utf-8 -*-

class Session(object):
    def __init__(self):
        self.responsed = False    # if responsed to client
        self.client_addr = None   # client addr
        self.req_data = None      # client request
        self.send_ts = 0          # ts to send to upstream
        self.server_resps = {}    # upstream Addr -> data
