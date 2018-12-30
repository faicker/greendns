#!/bin/sh

cmd="greendns -r greendns"

if [[ "${LISTEN}" ]]; then
    cmd="$cmd"" -p ${LISTEN}"
fi

if [[ "${LOGLEVEL}" ]]; then
    cmd="$cmd"" -l ${LOGLEVEL}"
fi

if [[ "${TIMEOUT}" ]]; then
    cmd="$cmd"" -t ${TIMEOUT}"
fi

if [[ "${LDS}" ]]; then
    cmd="$cmd"" --lds ${LDS}"
fi

if [[ "${RDS}" ]]; then
    cmd="$cmd"" --rds ${RDS}"
fi

if [[ "${CACHE}" == "true" ]]; then
    cmd="$cmd"" --cache"
fi

if [[ "$RFC1918" == "true" ]]; then
    cmd="$cmd"" --rfc1918"
fi

if [[ "${ROUTEFILE}" ]]; then
    cmd="$cmd"" -f ${ROUTEFILE}"
fi

if [[ "${BLACKLIST}" ]]; then
    cmd="$cmd"" -b ${BLACKLIST}"
fi

$cmd
