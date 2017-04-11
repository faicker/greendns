[![Build Status](https://travis-ci.org/faicker/pychinadns.svg?branch=master)](https://travis-ci.org/faicker/pychinadns)
[![Coverage Status](https://coveralls.io/repos/github/faicker/pychinadns/badge.svg?branch=master)](https://coveralls.io/github/faicker/pychinadns?branch=master)
# pychinadns

A DNS recursive resolve server to avoid result being poisoned and friendly to CDN. It will qeury dns servers at the same time.
You must config at least two dns servers. One is in China and the other is out of China which is not poisoned(tunnel through VPN or use OpenDNS 443/5353 port).

Use the response as follows,

```
First filter poisoned ip with block iplist with -b argument.
Second,
                           | result is local | result is foreign
     local dns server      |    A            |   B
     foreign dns server    |    C            |   D

AC: use local dns server result
AD: use local dns server result
BC: not possible. use foreign dns server result
BD: use foreign dns server result
```

## install
pip install .

## usage
```
pychinadns -r chinadns -u 223.5.5.5:53,208.67.222.222:5353 -l debug -f /usr/etc/pychinadns/chnroute.txt -b /usr/etc/pychinadns/iplist.txt
```
or
```
pychinadns -r chinadns -u 223.5.5.5:53,8.8.8.8:53 -l debug -f /usr/etc/pychinadns/chnroute.txt -b /usr/etc/pychinadns/iplist.txt
```

## configure

pychinadns -r chinadns -h

```
usage: chinadns.py [-h] [-r HANDLER] [-p PORT] [-u UPSTREAM] [-t TIMEOUT]
                   [-l LOGLEVEL] [-m MODE] -f CHNROUTE -b BLACKLIST
                   [--rfc1918] [--cache]

optional arguments:
  -h, --help
  -r HANDLER, --handler HANDLER
                        Specify handler class, chinadns|quickest (default:
                        None)
  -p PORT, --port PORT  Specify listen port or ip (default: 127.0.0.1:5353)
  -u UPSTREAM, --upstream UPSTREAM
                        Specify multiple upstream dns servers (default:
                        223.5.5.5:53,8.8.8.8:53)
  -t TIMEOUT, --timeout TIMEOUT
                        Specify upstream timeout (default: 1.0)
  -l LOGLEVEL, --log-level LOGLEVEL
                        Specify log level, debug|info|warning|error (default:
                        info)
  -m MODE, --mode MODE  Specify io loop mode, select|epoll (default: select)
  -f CHNROUTE, --chnroute CHNROUTE
                        Specify chnroute file (default: None)
  -b BLACKLIST, --blacklist BLACKLIST
                        Specify ip blacklist file (default: None)
  --rfc1918             Specify if rfc1918 ip is local (default: False)
  --cache               Specify if cache is enabled (default: False)
```

## Acknowledgements

+ @clowwindy: the author of the [ChinaDNS](https://github.com/shadowsocks/ChinaDNS)

## License

This project is under the MIT license. See the [LICENSE](LICENSE) file for the full license text.
