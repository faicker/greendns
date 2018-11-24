# -*- coding: utf-8 -*-
import select
import traceback
from greendns import timer

EV_READ = 1
EV_WRITE = 2


class IOLoop(object):
    MIN_INTERVAL = 0.05

    def __init__(self):
        self.rd_socks = {}    # sock -> callback
        self.wr_socks = {}
        self.err_callback = None
        self.tm = timer.TimerManager()

    def register(self, sock, events, callback, *args, **kwargs):
        if events & EV_READ:
            self.rd_socks[sock] = (callback, args, kwargs)
        if events & EV_WRITE:
            self.wr_socks[sock] = (callback, args, kwargs)
        return True

    def unregister(self, sock, events=EV_READ | EV_WRITE):
        if events & EV_READ:
            self.rd_socks.pop(sock, None)
        if events & EV_WRITE:
            self.wr_socks.pop(sock, None)
        return True

    def set_err_callback(self, callback, *args, **kwargs):
        self.err_callback = (callback, args, kwargs)
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
        self.rlist = list(self.rd_socks)
        self.wlist = list(self.wr_socks)
        s = set(self.rlist + self.wlist)
        self.elist = [f for f in s]

    def register(self, sock, events, callback, *args, **kwargs):
        super(Select, self).register(sock, events, callback, *args, **kwargs)
        self.__make_list()
        return True

    def unregister(self, sock, events=EV_READ | EV_WRITE):
        super(Select, self).unregister(sock, events)
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
                for sock in rl:
                    callback, args, kwargs = self.rd_socks.get(sock)
                    if callback:
                        callback(sock, *args, **kwargs)
                for sock in wl:
                    callback, args, kwargs = self.wr_socks.get(sock)
                    if callback:
                        callback(sock, *args, **kwargs)
                if self.err_callback:
                    for sock in el:
                        self.err_callback[0](sock, *self.err_callback[1],
                                             **self.err_callback[2])
            except Exception as e:
                print("exception, %s\n%s" % (e, traceback.format_exc()))


class Epoll(IOLoop):
    def __init__(self):
        super(Epoll, self).__init__()
        self.epoll = select.epoll()
        self.fd2socks = {}

    def register(self, sock, events, callback, *args, **kwargs):
        ev = select.EPOLLERR | select.EPOLLHUP
        need_modify = False
        if sock in self.rd_socks:
            ev |= select.EPOLLIN
            need_modify = True
        if sock in self.wr_socks:
            ev |= select.EPOLLOUT
            need_modify = True
        if events & EV_READ:
            ev |= select.EPOLLIN
        if events & EV_WRITE:
            ev |= select.EPOLLOUT
        if need_modify:
            self.epoll.modify(sock.fileno(), ev)
        else:
            try:
                self.epoll.register(sock.fileno(), ev)
            except IOError:
                return False
            else:
                self.fd2socks[sock.fileno()] = sock
        super(Epoll, self).register(sock, events, callback, *args, **kwargs)
        return True

    def unregister(self, sock, events=EV_READ | EV_WRITE):
        super(Epoll, self).unregister(sock, events)
        if events == EV_READ | EV_WRITE:
            self.epoll.unregister(sock)
            ck = self.fd2socks.pop(sock.fileno(), None)
            if ck:
                return True
            else:
                return False
        else:
            ev = select.EPOLLERR | select.EPOLLHUP | \
                select.EPOLLIN | select.EPOLLOUT
            if events & EV_READ:
                ev ^= select.EPOLLIN
            if events & EV_WRITE:
                ev ^= select.EPOLLOUT
            self.epoll.modify(sock.fileno(), ev)
            return True

    def run(self):
        while True:
            try:
                self.check_timer()
                events = self.epoll.poll(self.MIN_INTERVAL)
                for fd, event in events:
                    sock = self.fd2socks.get(fd)
                    if not sock:
                        continue
                    if event & select.EPOLLERR or event & select.EPOLLHUP:
                        if self.err_callback:
                            self.err_callback[0](sock, *self.err_callback[1],
                                                 **self.err_callback[2])
                    elif event & select.EPOLLIN:
                        callback, args, kwargs = self.rd_socks.get(sock)
                        if callback:
                            callback(sock, *args, **kwargs)
                    elif event & select.EPOLLOUT:
                        callback, args, kwargs = self.wr_socks.get(sock)
                        if callback:
                            callback(sock, *args, **kwargs)
            except Exception as e:
                print("exception, %s\n%s" % (e, traceback.format_exc()))


def get_ioloop(name="select"):
    if name == "epoll":
        return Epoll()
    elif name == "select":
        return Select()
    else:
        return None
