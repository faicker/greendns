#!/usr/bin/env bash
#output china route via default gw to stdout

cd `dirname ${BASH_SOURCE[0]}`

chnroute=$1
default_gw=$2
vpn_ip=$3

if [[ ! -f $chnroute || -z $default_gw || -z $vpn_ip ]]; then
    echo "usage: $0 chnroute_file default_gw_ip vpn_ip"
    exit 1
fi

while read net; do
    echo "$net via $default_gw"
done < $chnroute
echo "$vpn_ip via $default_gw"
