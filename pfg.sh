#!/usr/bin/env bash
pid=$1
if [[ $2 == "" ]]; then
    time=60
else
    time=$(( $2 * 60 ))
fi

when=$(date +"%F_%T") | sed 's/:/_/g'
cd ./FlameGraph
rm -f perf_*.data out_*.perf out_*.folded out_*.svg
perf record -F 99 -g -p ${pid} -o perf_$when.data -- sleep ${time} 
perf script perf_$when.data > out_$when.perf
./stackcollapse-perf.pl out_$when.perf > out_$when.folded
./flamegraph.pl out_$when.folded > out_$when.svg
echo "Please access http://$(hostname -i | awk '{print $1'):8000/out_$when.svg"
python3 -m http.server 8000
