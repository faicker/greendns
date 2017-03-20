# -*- coding: utf-8 -*-


class HandlerBase(object):
    def __init__(self):
        pass

    def add_arg(self, parser):
        pass

    def init(self, args):
        pass

    def __call__(self, req):
        pass
