#!/bin/bash

# Author: Nicolas Winsten, nicolasd.winsten@gmail.com
#
# This script uses CAT to estimate the working set of an app.
# It works by successively allocating more of the L3 cache to the app
# and terminates when it is determined that the app's data can reside
# in that allocation
#
# How to reliably determine if the app fully resides in an allocation?
# Here I just set a threshold for the number of LLC-misses read from perf.
# Once that metric falls below a certain threshold, terminate
#
# Possibly, there's a more reliable 


CACHE_WAYS=20
CACHE_LINE_SZ=64

# optional argument defaults
cpu=18			# cpu to profile on
threshold=50000		# below this threshold means negligible misses
timeout=0		# how long to profile for

while getopts 'c:m:t:h' opt; do
  case "$opt" in
    c)
      cpu=$OPTARG
      ;;

    m)
      threshold=$OPTARG
      ;;

    t)
      timeout=$OPTARG
      ;;

    :|?|h)
      echo "Usage: $(basename $0) [-c cpu] [-t timeout] [-m misses threshold] command"
      exit 1
      ;;
  esac
done

shift "$(($OPTIND -1))"
command=$@
MISSES=0
TIME=0

[ -z "$command" ] \
  && (echo "Usage: $(basename $0) [-c cpu] [-t timeout] [-m misses threshold] command") \
  && exit 1

# profile n -- profiles the command given n cache ways
function profile {
  # setup CAT allocations
  mask1=$((0xfffff >> (20 - $1)))
  mask2=$((0xfffff & ~ mask1))
  pqos -e "llc:1=$mask1;llc:2=$mask2;" 2>&1 > /dev/null \
  && pqos -a "llc:1=$cpu;llc:2=$((cpu + 1))" 2>&1> /dev/null \
  || ( echo Something went wrong with CAT; exit 1 )
  
  # where to run the counterbalancing program?
  # just run it on the next logical cpu
  taskset -c $((cpu + 1)) $command >/dev/null & pid=($!)
 
  # profile the program with perf and collect total misses and user time
  # should we also capture LLC-store-misses?
  res=$( taskset -c $cpu perf stat --no-big-num -e LLC-load-misses timeout ${timeout}s $command 2>&1 >/dev/null \
  | awk '/LLC-(load|store)-misses/ {misses+=$1} /seconds user/ {time=$1} END {print misses, time}' )
  
  # kill the counterbalance program
  kill $pid  

  MISSES=$(echo $res | awk '{print $1}')
  TIME=$(echo $res | awk '{print $2}')
  echo found $MISSES misses in $TIME seconds
}

# reset CAT allocations
pqos -R	|| (echo Something went wrong with CAT; exit 1)

incache=0
ways=1
while [ $ways -le $CACHE_WAYS ]
do
  profile $ways

  if [ $MISSES -lt $threshold ]
  then incache=1; break
  fi

  ways=$((ways+1))
done

BANDWIDTH=$(echo "($MISSES * $CACHE_LINE_SZ) / $TIME" | bc -l)

# TODO use getconf -a | grep CACHE to find L3 cache size
if [ $incache -eq 1 ] 
then echo command fits into $ways ways
else echo command does not fit in $ways ways
fi
echo BANDWIDTH $BANDWIDTH bytes per sec

