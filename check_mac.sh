#!/bin/bash


host_mac=$1

qemu_ip=$(arp -n | grep -w -i $host_mac | awk '{print $1}')

printf "%s" $qemu_ip