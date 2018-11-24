#!/usr/bin/env bash

cd `dirname ${BASH_SOURCE[0]}`

curl 'http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest' | grep ipv4 | grep -E '(CN|HK)' | awk -F\| '{ printf("%s/%d\n", $4, 32-log($5)/log(2)) }' > localroute.txt
