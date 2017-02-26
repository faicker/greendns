#pychinadns

A DNS recursive resolve server to avoid result being poisoned and friendly to CDN. It will qeury dns servers at the same time.
You must config at least two dns servers. One is in China and the other is out of China which is not poisoned.

The response is,

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

## usage

```
python /root/pychinadns/src/chinadns.py -r ChinaDNSReponseHandler -u 223.5.5.5:53,8.8.8.8:53 -l debug -f /root/pychinadns/conf/chnroute.txt -b /root/pychinadns/conf/iplist.txt
```

## configure

./chinadns.py -r ChinaDNSReponseHandler -h

```
usage: chinadns.py [-h] [-r HANDLER] [-p PORT] [-u UPSTREAM] [-t TIMEOUT]
                   [-l LOGLEVEL] -f CHNROUTE [--rfc1918] -b BLACKLIST

optional arguments:
  -h, --help            show this help message and exit
  -r HANDLER, --handler HANDLER
                        Specify response handler,
                        QuickestResponseHandler|ChinaDNSReponseHandler
                        (default: QuickestResponseHandler)
  -p PORT, --port PORT  Specify listen port or ip (default: 127.0.0.1:5353)
  -u UPSTREAM, --upstream UPSTREAM
                        Specify multiple upstream dns servers (default:
                        223.5.5.5:53,8.8.8.8:53)
  -t TIMEOUT, --timeout TIMEOUT
                        Specify upstream timeout (default: 1.0)
  -l LOGLEVEL, --log-level LOGLEVEL
                        Specify log level, debug|info|warning|error (default:
                        info)
  -f CHNROUTE, --chnroute CHNROUTE
                        Specify chnroute file (default: None)
  --rfc1918             Specify if rfc1918 ip is local (default: False)
  -b BLACKLIST, --blacklist BLACKLIST
                        Specify ip blacklist file (default: None)
```

## Acknowledgements

+ @clowwindy: the author of the [ChinaDNS](https://github.com/shadowsocks/ChinaDNS)

## License

This project is under the MIT license. See the [LICENSE](LICENSE) file for the full license text.
