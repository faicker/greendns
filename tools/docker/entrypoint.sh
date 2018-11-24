#!/bin/sh

cmd="greendns -r greendns -p ${LISTEN} -u ${IDNS},${ODNS} -l ${LOGLEVEL} -t ${TIMEOUT} -f /usr/local/etc/greendns/localroute.txt -b /usr/local/etc/greendns/iplist.txt"

if [[ "${CACHE}" == "true" ]]; then
    cmd="$cmd"" --cache"
fi

if [[ "$RFC1918" == "true" ]]; then
    cmd="$cmd"" --rfc1918"
fi

$cmd
