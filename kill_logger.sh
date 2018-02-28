#!/bin/bash

#log="/tmp/taskgen_qemusession_ip_kill.log"
log=$1



until [ -f $log ]
    do
        sleep 1
    done

#Read the last lien of kill_log 
kill_ip=$(tail -f -n1 $log)

printf "%s" $kill_ip

