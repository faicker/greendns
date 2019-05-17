
## collect
* run this command and then dnsperf.sh
* after dnsperf.sh end, ctrl+c this command

```bash
python -mcProfile -o greendns.profile ../greendns/server.py -r greendns -l warn --lds 192.168.150.3:53 --rds 127.0.0.1:5454 --rfc1918 -f ../etc/greendns/localroute.txt -b ../etc/greendns/iplist.txt > a.log 2>&1
```

### view

```bash
gprof2dot -f pstats ./greendns.profile | dot -Tpng -o greendns.png
```
