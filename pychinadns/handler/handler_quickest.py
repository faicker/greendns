# -*- coding: utf-8 -*-
import sys
import handler_base


class QuickestResponseHandler(handler_base.HandlerBase):
    def __init__(self):
        pass

    def add_arg(self, parser):
        pass

    def init(self, args):
        pass

    def __call__(self, req):
        resp = ""
        if req.server_num > 0:
            least_ts = sys.maxint
            least_upstream = None
            for upstream, ts in req.resp_ts.iteritems():
                if ts < least_ts:
                    least_ts = ts
                    least_upstream = upstream
            resp = req.server_resps[least_upstream]
        return resp
