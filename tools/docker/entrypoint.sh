#!/bin/sh

cmd="pychinadns -r chinadns -p ${LISTEN} -u ${IDNS},${ODNS} -l ${LOGLEVEL} -t ${TIMEOUT} -f /usr/local/etc/pychinadns/chnroute.txt -b /usr/local/etc/pychinadns/iplist.txt"

if [[ "${CACHE}" == "true" ]]; then
    cmd="$cmd"" --cache"
fi

if [[ "$RFC1918" == "true" ]]; then
    cmd="$cmd"" --rfc1918"
fi

$cmd
