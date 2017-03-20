# -*- coding: utf-8 -*-
from pychinadns.timer import Timer
from pychinadns.timer import TimerManager
import time


class TestTimer(object):
    def callback(self):
        self.run = True

    def test_lt(self):
        now_ts = time.time()
        t1 = Timer(now_ts, 3, self.callback, True)
        t2 = Timer(now_ts, 4, self.callback, True)
        assert t1 < t2

    def test_run(self):
        self.run = False
        now_ts = time.time()
        t1 = Timer(now_ts, 3, self.callback, True)
        assert int(t1.next_run_ts) == int(now_ts) + 3
        t1.run()
        assert self.run is True
        assert int(t1.next_run_ts) == int(now_ts) + 6


class TestTimerManager(object):
    def callback(self):
        self.run = True

    def test_add_timer(self):
        tm = TimerManager()
        tm.add_timer(5, self.callback, True)
        tm.add_timer(3, self.callback, True)
        tm.add_timer(8, self.callback, True)
        t1 = tm.timers.queue[0]
        t2 = tm.timers.queue[1]
        t3 = tm.timers.queue[2]
        assert t1.interval == 3
        assert t1 < t2 < t3

    def test_check_timer_once(self):
        tm = TimerManager()
        tm.add_timer(2, self.callback, True)
        time.sleep(2)
        self.run = False
        tm.check_timer()
        assert self.run is True
        assert len(tm.timers.queue) == 0

    def test_check_timer_cron(self):
        tm = TimerManager()
        tm.add_timer(2, self.callback, False)
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
