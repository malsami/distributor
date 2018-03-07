#!/bin/bash

#log="/tmp/taskgen_qemusession_ip_kill.log"
log=$1



until [ -f $log ]
    do
        sleep 1
    done

#Read the last line of kill_log, if it is not empty, then it will yield the ip address to kill
kill_ip=$(tail -f -n0 $log 2> /dev/null)

printf "%s" $kill_ip

