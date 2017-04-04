# -*- coding: utf-8 -*-
import select
import timer
import traceback

EV_READ = 1
EV_WRITE = 2


class IOLoop(object):
    MIN_INTERVAL = 0.05

    def __init__(self):
        self.rd_fds = {}    # fd -> callback
        self.wr_fds = {}
        self.err_callback = None
        self.tm = timer.TimerManager()

    def register(self, fd, events, callback):
        if events & EV_READ:
            self.rd_fds[fd] = callback
        if events & EV_WRITE:
            self.wr_fds[fd] = callback
        return True

    def unregister(self, fd):
        if fd in self.rd_fds:
            del self.rd_fds[fd]
        if fd in self.wr_fds:
            del self.wr_fds[fd]
        return True

    def set_err_callback(self, callback):
        self.err_callback = callback
        return True

    def run(self):
        pass

    def check_timer(self):
        self.tm.check_timer()

    def add_timer(self, is_once, seconds, callback, *args, **kwargs):
        self.tm.add_timer(is_once, seconds, callback, *args, **kwargs)


class Select(IOLoop):
    def __init__(self):
        super(Select, self).__init__()
        self.rlist = []
        self.wlist = []
        self.elist = []

    def __make_list(self):
        self.rlist = list(self.rd_fds)
        self.wlist = list(self.wr_fds)
        s = set(self.rlist + self.wlist)
        self.elist = [f for f in s]

    def register(self, fd, events, callback):
        super(Select, self).register(fd, events, callback)
        self.__make_list()
        return True

    def unregister(self, fd):
        super(Select, self).unregister(fd)
        self.__make_list()
        return True

    def run(self):
        if len(self.rlist) == 0 and len(self.wlist) == 0:
            return
        while True:
            try:
                self.check_timer()
                (rl, wl, el) = select.select(self.rlist, self.wlist,
                                             self.elist, self.MIN_INTERVAL)
                for fd in rl:
                    if fd in self.rd_fds:
                        self.rd_fds[fd](fd)
                for fd in wl:
                    if fd in self.wr_fds:
                        self.wr_fds[fd](fd)
                if self.err_callback:
                    for fd in el:
                        self.err_callback(fd)
            except Exception as e:
                print("exception, %s\n%s" % (e, traceback.format_exc()))


class Epoll(IOLoop):
    def __init__(self):
        super(Epoll, self).__init__()
        self.epoll = select.epoll()

    def register(self, fd, events, callback):
        ev = select.EPOLLERR | select.EPOLLHUP
        if events & EV_READ:
            ev |= select.EPOLLIN
        if events & EV_WRITE:
            ev |= select.EPOLLOUT
        try:
            self.epoll.register(fd, ev)
        except IOError:
            return False
        super(Epoll, self).register(fd, events, callback)
        return True

    def unregister(self, fd):
        super(Epoll, self).unregister(fd)
        self.epoll.unregister(fd)
        return True

    def run(self):
        while True:
            try:
                self.check_timer()
                events = self.epoll.poll(self.MIN_INTERVAL)
                for fd, event in events:
                    if event & select.EPOLLERR or event & select.EPOLLHUP:
                        if self.err_callback:
                            self.err_callback(fd)
                    elif event & select.EPOLLIN:
                        if fd in self.rd_fds:
                            self.rd_fds[fd](fd)
                    elif event & select.EPOLLOUT:
                        if fd in self.wr_fds:
                            self.wr_fds[fd](fd)
            except Exception as e:
                print("exception, %s\n%s" % (e, traceback.format_exc()))


def get_ioloop(name="select"):
    if name == "epoll":
        return Epoll()
    elif name == "select":
        return Select()
    else:
        return None
