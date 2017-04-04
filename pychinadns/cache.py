# -*- coding: utf-8 -*-
import time
import six


class Cache(object):
    def __init__(self):
        self.m = {}

    def __len__(self):
        return len(self.m)

    def iteritems(self):
        return six.iteritems(self.m)

    def add(self, key, value, ttl):
        self.m[key] = (value, time.time() + ttl)

    def remove(self, key):
        self.m.pop(key, None)

    def find(self, key):
        v = self.m.get(key)
        if v:
            value, expire_ts = v
            if time.time() >= expire_ts:
                self.remove(key)
                return None
            else:
                return value
        return None

    def validate(self):
        expired_key = []
        for k, v in six.iteritems(self.m):
            value, expire_ts = v
            if time.time() >= expire_ts:
                expired_key.append(k)
        for k in expired_key:
            self.remove(k)
