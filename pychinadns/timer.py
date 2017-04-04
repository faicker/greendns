# -*- coding: utf-8 -*-
import time
from six.moves import queue


class Timer(object):
    def __init__(self, now_ts, is_once, interval, callback, *args, **kwargs):
        self.interval = interval
        self.callback = callback
        self.is_once = is_once
        self.args = args
        self.kwargs = kwargs
        self.next_run_ts = now_ts + interval

    def __lt__(self, other):
        return self.next_run_ts < other.next_run_ts

    def run(self):
        self.callback(*self.args, **self.kwargs)
        self.next_run_ts += self.interval


class TimerManager(object):
    def __init__(self):
        self.timers = queue.PriorityQueue()

    def add_timer(self, is_once, interval, callback, *args, **kwargs):
        t = Timer(time.time(), is_once, interval, callback, *args, **kwargs)
        self.timers.put(t)

    def check_timer(self):
        now_ts = time.time()
        readd = []
        while not self.timers.empty():
            t = self.timers.queue[0]
            if now_ts < t.next_run_ts:
                break
            self.timers.get()
            t.run()
            if not t.is_once:
                readd.append(t)
        for t in readd:
            self.timers.put(t)
