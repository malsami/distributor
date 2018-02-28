#!/bin/bash

#log="/tmp/taskgen_qemusession_ip_kill.log"
log=$1



until [ -f $log ]
    do
        sleep 1
    done

    # read file and kill own qemu instance if necessary
#tail -f -n0 $log | read $kill_ip 
kill_ip=$(tail -f -n0 $log)

printf "%s" $kill_ip

