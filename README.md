[![Build Status](https://travis-ci.org/faicker/greendns.svg?branch=master)](https://travis-ci.org/faicker/greendns)
[![Coverage Status](https://coveralls.io/repos/github/faicker/greendns/badge.svg?branch=master)](https://coveralls.io/github/faicker/greendns?branch=master)

# greendns

A DNS recursive resolve server to avoid result being poisoned and friendly to CDN. It will qeury dns servers at the same time. It's more efficient and quicker than [ChinaDNS](https://github.com/shadowsocks/ChinaDNS)
You must config at least two dns servers. A part is local and poisoned, the other part is unpoisoned(tunnel through VPN or use OpenDNS 443/5353 port, [dnscrypt-proxy](https://github.com/jedisct1/dnscrypt-proxy) is recommended)

## How it works

```
First filter poisoned ip with blocked iplist with -b argument.
Second,
                                        | returned ip is local | returned ip is foreign
     local and poisoned dns server      |    A                 |   B
     unpoisoned dns server              |    C                 |   D

From the matrix, we get the result as follows,
AC: use local dns server result
AD: use local dns server result
BC: impossible. use unpoisoned dns server result
BD: use unpoisoned dns server result
```

It has two assumptions,
* the polluted domain is foreign.
* the poisoned result ip is foreign.

## Install

```bash
$ pip install greendns
```

## Usage

```bash
$ greendns -r greendns -u 223.5.5.5:53,208.67.222.222:5353 -l debug -f /usr/etc/greendns/localroute.txt -b /usr/etc/greendns/iplist.txt
```
or if 8.8.8.8 is unpoisoned,

```bash
$ greendns -r greendns -u 223.5.5.5:53,8.8.8.8:53 -l debug -f /usr/etc/greendns/localroute.txt -b /usr/etc/greendns/iplist.txt
```

## Configure

```bash
$ greendns -r greendns -h
usage: greendns.py [-h] [-r HANDLER] [-p PORT] [-u UPSTREAM] [-t TIMEOUT]
                   [-l LOGLEVEL] [-m MODE] -f LOCALROUTE -b BLACKLIST
                   [--rfc1918] [--cache]

optional arguments:
  -h, --help
  -r HANDLER, --handler HANDLER
                        Specify handler class, greendns|quickest (default:
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
  -f LOCALROUTE, --localroute LOCALROUTE
                        Specify local routes file (default: None)
  -b BLACKLIST, --blacklist BLACKLIST
                        Specify ip blacklist file (default: None)
  --rfc1918             Specify if rfc1918 ip is local (default: False)
  --cache               Specify if cache is enabled (default: False)
```

## Acknowledgements

+ @clowwindy: the author of the [ChinaDNS](https://github.com/shadowsocks/ChinaDNS)

## License

This project is under the MIT license. See the [LICENSE](LICENSE) file for the full license text.
