# -*- coding: utf-8 -*-
from greendns import request


class HandlerBase(object):
    def __init__(self):
        pass

    def add_arg(self, parser):
        pass

    def parse_arg(self, parser, remaining_argv, args):
        pass

    def init(self, io_engine):
        pass

    def get_request(self):
        return request.Request()

    def on_client_request(self, req):
        return (True, None)

    def on_upstream_response(self, req):
        return None

    def on_timeout(self, req, timeout):
        return (True, None)
