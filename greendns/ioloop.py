# -*- coding: utf-8 -*-
import select
from greendns import timer

EV_READ = 1
EV_WRITE = 2


class IOLoop(object):
    MIN_INTERVAL = 0.05

    def __init__(self):
        self.rd_socks = {}    # sock -> callback
        self.wr_socks = {}
        self.err_callback = None
        self.running = True
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

    def on_close_sock(self, sock):
        pass

    def set_err_callback(self, callback, *args, **kwargs):
        self.err_callback = (callback, args, kwargs)
        return True

    def run(self):
        pass

    def stop(self):
        self.running = False

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
        self.elist = list(s)

    def register(self, sock, events, callback, *args, **kwargs):
        super(Select, self).register(sock, events, callback, *args, **kwargs)
        self.__make_list()
        return True

    def unregister(self, sock, events=EV_READ | EV_WRITE):
        super(Select, self).unregister(sock, events)
        self.__make_list()
        return True

    def on_close_sock(self, sock):
        self.unregister(sock)

    def run(self):
        if not self.rlist and not self.wlist:
            return
        while self.running:
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


class Epoll(IOLoop):
    def __init__(self):
        super(Epoll, self).__init__()
        self.epoll = select.epoll()
        self.fd2socks = {}

    def register(self, sock, events, callback, *args, **kwargs):
        ev = select.EPOLLERR | select.EPOLLHUP
        need_modify = False
        if sock.fileno() in self.fd2socks:
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
            except (IOError, OSError):
                return False
            else:
                self.fd2socks[sock.fileno()] = sock
        return super(Epoll, self).register(sock, events, callback, *args, **kwargs)

    def unregister(self, sock, events=EV_READ | EV_WRITE):
        if not super(Epoll, self).unregister(sock, events):
            return False
        ev = select.EPOLLERR | select.EPOLLHUP | \
            select.EPOLLIN | select.EPOLLOUT
        if events & EV_READ:
            ev ^= select.EPOLLIN
        if events & EV_WRITE:
            ev ^= select.EPOLLOUT
        self.epoll.modify(sock.fileno(), ev)
        return True

    def on_close_sock(self, sock):
        super(Epoll, self).unregister(sock)
        self.epoll.unregister(sock)
        self.fd2socks.pop(sock.fileno())

    def run(self):
        while self.running:
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
                if event & select.EPOLLIN:
                    result = self.rd_socks.get(sock)
                    if not result:
                        continue
                    callback, args, kwargs = result
                    if callback:
                        callback(sock, *args, **kwargs)
                if event & select.EPOLLOUT:
                    result = self.wr_socks.get(sock)
                    if not result:
                        continue
                    callback, args, kwargs = result
                    if callback:
                        callback(sock, *args, **kwargs)


def get_ioloop(name="select"):
    if name == "epoll":
        return Epoll()
    if name == "select":
        return Select()
    return None
