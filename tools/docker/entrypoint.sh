#!/bin/sh

pychinadns -r chinadns -p ${LISTEN} -u ${IDNS},${ODNS} -l ${LOGLEVEL} -f /usr/local/etc/pychinadns/chnroute.txt -b /usr/local/etc/pychinadns/iplist.txt --cache --rfc1918
