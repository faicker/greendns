# -*- coding: utf-8 -*-
from greendns.timer import Timer
from greendns.timer import TimerManager
import time


class TestTimer(object):
    def callback(self):
        self.run = True

    def test_lt(self):
        now_ts = time.time()
        t1 = Timer(now_ts, True, 3, self.callback)
        t2 = Timer(now_ts, True, 4, self.callback)
        assert t1 < t2

    def test_run(self):
        self.run = False
        now_ts = time.time()
        t1 = Timer(now_ts, True, 3, self.callback)
        assert int(t1.next_run_ts) == int(now_ts) + 3
        t1.run()
        assert self.run is True
        assert int(t1.next_run_ts) == int(now_ts) + 6


class TestTimerManager(object):
    def callback(self):
        self.run = True

    def test_add_timer(self):
        tm = TimerManager()
        tm.add_timer(True, 5, self.callback)
        tm.add_timer(True, 3, self.callback)
        tm.add_timer(True, 8, self.callback)
        t1 = tm.timers.queue[0]
        t2 = tm.timers.queue[1]
        t3 = tm.timers.queue[2]
        assert t1.interval == 3
        assert t1 < t2 < t3

    def test_check_timer_once(self):
        tm = TimerManager()
        tm.add_timer(True, 2, self.callback)
        time.sleep(2)
        self.run = False
        tm.check_timer()
        assert self.run is True
        assert len(tm.timers.queue) == 0

    def test_check_timer_cron(self):
        tm = TimerManager()
        tm.add_timer(False, 2, self.callback)
        time.sleep(2)
        self.run = False
        tm.check_timer()
        assert self.run is True
        assert len(tm.timers.queue) == 1
        time.sleep(2)
        self.run = False
        tm.check_timer()
        assert self.run is True
        assert len(tm.timers.queue) == 1
