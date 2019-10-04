#!/bin/bash

# Add directory containing this script to PATH
PATH="$(dirname $0):${PATH}"

hostname=`hostname -s`

function getip() {
  out=$(host $1) && echo $out | awk '{print $NF}'
}

myip=$(getip $(hostname))

function init() {
  instance=0
  mask=0x003f
  bindhost=eth5
  netcpu=0
  outcpu=3

  if [ $USE_BDA -eq 1 ]
  then
    netthread=hera_catcher_net_thread_bda
    diskthread=hera_catcher_disk_thread_bda
  else
    netthread=hera_catcher_net_thread
    diskthread=hera_catcher_disk_thread
  fi

  echo "Using netthread: $netthread"
  echo "Using diskthread: $diskthread"
  
  echo taskset $mask \
  hashpipe -p paper_gpu -I $instance \
    -o BINDHOST=$bindhost \
    -c $netcpu $netthread \
    -c $outcpu $diskthread

  taskset $mask \
  hashpipe -p paper_gpu -I $instance \
    -o BINDHOST=$bindhost \
    -c $netcpu $netthread \
    -c $outcpu $diskthread \
     < /dev/null \
    1> ~/catcher.out.$instance \
    2> ~/catcher.err.$instance &
}

# Default to not using BDA version
USE_BDA=0

for arg in $@; do
  case $arg in
    -h)
      echo "Usage: $(basename $0) [-a] INSTANCE_ID [...]"
      echo "   -a: Use baseline dependent averaging threads"
      exit 0
    ;;

    -a)
      USE_BDA=1
      shift
    ;;
  esac
done

if [ -z "$1" ]
then
  echo "Usage: $(basename $0) [-a] INSTANCE_ID [...]"
  echo "   -a: Use baseline dependent averaging threads"
  exit 1
fi

for instidx in "$@"
do
  echo Starting instance catcher/$instidx
  init
  echo Instance catcher/$instidx pid $!
  # Sleep to let instance come up
  sleep 10
done

# Zero out MISSEDPK counts
for instidx in "$@"
do
  echo Resetting MISSEDPK counts for catcher/$instidx
  hashpipe_check_status -I $instidx -k MISSEDPK -s 0
done
