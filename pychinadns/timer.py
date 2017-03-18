#!/usr/bin/env python
# coding=utf-8
import time
import Queue


class Timer(object):
    def __init__(self, now_ts, interval, callback, is_once):
        self.interval = interval
        self.callback = callback
        self.is_once = is_once
        self.next_run_ts = now_ts + interval

    def __lt__(self, other):
        return self.next_run_ts < other.next_run_ts

    def Run(self):
        self.callback()
        self.next_run_ts += self.interval


class TimerManager(object):
    def __init__(self):
        self.timers = Queue.PriorityQueue()

    def AddTimer(self, interval, callback, is_once=False):
        t = Timer(time.time(), interval, callback, is_once)
        self.timers.put(t)

    def CheckTimer(self):
        now_ts = time.time()
        readd = []
        while not self.timers.empty():
            t = self.timers.queue[0]
            if now_ts < t.next_run_ts:
                break
            self.timers.get()
            t.Run()
            if not t.is_once:
                readd.append(t)
        for t in readd:
            self.timers.put(t)
