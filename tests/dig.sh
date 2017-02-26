for j in `seq 10`; do
    for i in `seq 50`; do
        dig www.a.com @127.0.0.1 -p 5353 +tries=1 | grep time &
    done
    wait
done
