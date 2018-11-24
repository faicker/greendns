# -*- coding: utf-8 -*-
from greendns import handler_base
from greendns import request


class QuickestRequest(request.Request):
    def __init__(self):
        super(QuickestRequest, self).__init__()
        self.responsed = False


class QuickestHandler(handler_base.HandlerBase):
    def get_request(self):
        return QuickestRequest()

    def on_upstream_response(self, req):
        if not req.responsed:
            for upstream, data in req.server_resps.items():
                req.responsed = True
                return data
        return ""
