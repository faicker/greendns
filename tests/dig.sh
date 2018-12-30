for j in `seq 10`; do
    echo "round $j"
    for i in `seq 50`; do
        dig www.qq.com @127.0.0.1 -p 1053 +tries=1 | grep time &
    done
    wait
done
