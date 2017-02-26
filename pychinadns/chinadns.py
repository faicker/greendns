#!/usr/bin/env python
# coding=utf-8
import sys
import ConfigParser
import logging
import inspect
import argparse
import forwarder
import handler

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

def check_handler(value):
    h = None
    for name in dir(handler):
        if name == value:
            cls = getattr(handler, name)
            if inspect.isclass(cls):
                h = cls()
                if callable(h):
                    return h
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
        handle_parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            add_help=False,
        )
        handle_parser.add_argument("-r", "--handler", type=check_handler,
                            help="Specify response handler, QuickestResponseHandler|ChinaDNSReponseHandler",
                            default="QuickestResponseHandler")
        args, remaining_argv = handle_parser.parse_known_args()

        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            parents=[handle_parser]
        )
        parser.add_argument("-p", "--port",
                            help="Specify listen port or ip",
                            default="127.0.0.1:5353")
        parser.add_argument("-u", "--upstream",
                            help="Specify multiple upstream dns servers",
                            default="223.5.5.5:53,8.8.8.8:53")
        parser.add_argument("-t", "--timeout", type=float,
                            help="Specify upstream timeout",
                            default="1.0")
        parser.add_argument("-l", "--log-level", dest="loglevel", type=check_loglevel,
                            help="Specify log level, debug|info|warning|error",
                            default="info")
        args.handler.add_arg(parser)
        parser.parse_args(remaining_argv, namespace=args)

        if args.port.find(':') == -1:
            args.listen = "127.0.0.1:%s" %(args.port)
        else:
            args.listen = args.port
        return args

    def setup_logger(self):
        logger = logging.getLogger()
        ch = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s]: %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.setLevel(str2level[self.args.loglevel])
        return logger

    def start_resolver(self):
        h = self.args.handler
        h.init(self.args)
        self.resolver = forwarder.Forwarder(self.args.upstream,
                                          self.args.listen,
                                          self.args.timeout,
                                          h)
        self.resolver.run_forever()

def main():
    dns = ChinaDNS()
    dns.start_resolver()

if __name__ == "__main__":
    main()
