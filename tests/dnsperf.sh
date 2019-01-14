#!/usr/bin/env bash

cd `dirname ${BASH_SOURCE[0]}`

qps=1500
period=20

dnsperf -p 1053 -S 3 -Q $qps -d ./domain.txt -l $period
