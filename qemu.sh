#!/bin/bash

#Naked Variables 
mac=0a:06:00:00:00:$(printf %x $1)
bridge=br0
ip=10.200.45.$1
tap=tap$1
cur=$(pwd)
image="../image.elf" #input genode image

#creating tap device
sudo ip tuntap add name $tap mode tap
#adding it to the bridge
sudo brctl addif $bridge $tap
#setting it to UP
sudo ip link set dev $tap up

taskset -c $(($1 * 2 - 2)),$(($1 * 2 - 1)) screen -dmS qemu$1 bash -c "qemu-system-arm -net tap,ifname=$tap,script=no,downscript=no -net nic,macaddr=$mac,model=lan9118 -nographic -smp 4  -m 1024 -M realview-pbx-a9 -kernel $image >> $cur/../distributor_service/log/$1genode_dump.txt"
