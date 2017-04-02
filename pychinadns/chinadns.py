# -*- coding: utf-8 -*-
import sys
import os
import logging
import inspect
import argparse
import forwarder
import ioloop


str2level = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}


def check_loglevel(value):
    if value not in str2level:
        raise argparse.ArgumentTypeError("%s is an invalid log level" % value)
    return value


def load_mod(name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dir_path)
    n = "handler_" + name
    try:
        mod = __import__(n)
    except ImportError as e:
        print("err=%s, can't import file %s" % (e, n))
        sys.exit(1)
    sys.path.remove(dir_path)
    return mod


def check_handler(value):
    h = None
    base_mod = load_mod("base")
    base_cls = getattr(base_mod, "HandlerBase")
    mod = load_mod(value)
    for v in dir(mod):
        cls = getattr(mod, v)
        if inspect.isclass(cls) and issubclass(cls, base_cls):
            return cls()
    if h is None:
        raise argparse.ArgumentTypeError("%s is an invalid handler" % value)


class ChinaDNS(object):
    '''
        A DNS recursive resolve server to avoid result being poisoned.
    '''
    def __init__(self):
        self.args = self.parse_config()
        self.logger = self.setup_logger()

    def parse_config(self, argv=None):
        if argv is None:
            argv = sys.argv
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            add_help=False,
        )
        parser.add_argument("-h", "--help", action="store_true")
        parser.add_argument("-r", "--handler", type=check_handler,
                            help="Specify handler class, chinadns")
        args, remaining_argv = parser.parse_known_args()
        if args.handler is None:
            parser.print_help()
            sys.exit(0)

        parser.add_argument("-p", "--port",
                            help="Specify listen port or ip",
                            default="127.0.0.1:5353")
        parser.add_argument("-u", "--upstream",
                            help="Specify multiple upstream dns servers",
                            default="223.5.5.5:53,8.8.8.8:53")
        parser.add_argument("-t", "--timeout", type=float,
                            help="Specify upstream timeout",
                            default="1.0")
        parser.add_argument("-l", "--log-level", dest="loglevel",
                            type=check_loglevel,
                            help="Specify log level, debug|info|warning|error",
                            default="info")
        parser.add_argument("-m", "--mode", dest="mode",
                            help="Specify io loop mode, select|epoll",
                            default="select")
        _, remaining_argv = parser.parse_known_args(namespace=args)
        args.handler.add_arg(parser)
        if args.help:
            parser.print_help()
            sys.exit(0)
        args.handler.parse_arg(parser, remaining_argv, args)

        if args.port.find(':') == -1:
            args.listen = "127.0.0.1:%s" % (args.port)
        else:
            args.listen = args.port
        return args

    def setup_logger(self):
        logger = logging.getLogger()
        ch = logging.StreamHandler()
        fmt = '[%(asctime)s][%(levelname)s]: %(message)s'
        formatter = logging.Formatter(fmt)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.setLevel(str2level[self.args.loglevel])
        return logger

    def start_resolver(self):
        io_engine = ioloop.get_ioloop(self.args.mode)
        h = self.args.handler
        h.init(io_engine)
        self.resolver = forwarder.Forwarder(io_engine, self.args.upstream,
                                            self.args.listen,
                                            self.args.timeout,
                                            h)
        self.resolver.run_forever()


def main():
    dns = ChinaDNS()
    dns.start_resolver()

if __name__ == "__main__":
    main()
