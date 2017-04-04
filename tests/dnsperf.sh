#!/usr/bin/env bash

dnsperf -p 1053 -S 3 -Q 50 -d ./domain.txt -l 10
