#!/usr/bin/env bash

qps=50
period=20

dnsperf -p 1053 -S 3 -Q $qps -d ./domain.txt -l $period
