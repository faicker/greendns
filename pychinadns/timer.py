#!/usr/bin/env python
# coding=utf-8
import time
import Queue


class Timer(object):
    def __init__(self, now_ts, seconds, callback):
        self.seconds = seconds
        self.callback = callback
        self.next_run_ts = now_ts + seconds

    def __lt__(self, other):
        return self.next_run_ts < other.next_run_ts

    def Run(self):
        self.callback()
        self.next_run_ts += self.seconds


class TimerManager(object):
    def __init__(self):
        self.timers = Queue.PriorityQueue()

    def AddTimer(self, seconds, callback):
        t = Timer(int(time.time()), seconds, callback)
        self.timers.put(t)

    def CheckTimer(self):
        readd = []
        while not self.timers.empty():
            t = self.timers.get()
            readd.append(t)
            if int(time.time()) >= t.next_run_ts:
                t.Run()
            else:
                break
        for t in readd:
            self.timers.put(t)
