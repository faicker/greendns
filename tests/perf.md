## dnsperf

* CPU is Intel(R) Core(TM) i3-6100 CPU @ 3.70GHz
* local lan
* greendns loglevel is warning, cached disabled and mode is select.
* upstreams cache the result all the time


### for 2 udp upstream

##### Average packet size:  request 22, response 86 (4 A records)

max qps is 1850 with no error and latency is <78ms

##### Average packet size:  request 22, response 344(4 A records, 4 NS records, 8 ns A records)
max qps is 950 with no error and latency is <150ms

* dns parsing is slow.

### for 1 udp upstream and 1 tcp upstream(dnsmasq)

##### Average packet size:  request 22, response 86 (4 A records)

max qps is 1100 with no error and latency is <1.8s

* Greendns cpu is abount 80%. Dnsmasq cpu is about 80%.
