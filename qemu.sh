#!/bin/bash

#Naked Variables 
mac=0a:06:00:00:00:$(printf %x $1)
bridge=br0
ip=10.200.45.$1
tap=tap$1
image="../image.elf" #input genode image

#creating tap device
sudo ip tuntap add name $tap mode tap
#adding it to the bridge
sudo brctl addif $bridge $tap
#setting it to UP
sudo ip link set dev $tap up

screen -dmS qemu$1 bash -c "qemu-system-arm -net tap,ifname=$tap,script=no,downscript=no -net nic,macaddr=$mac,model=lan9118 -nographic -smp 4  -m 1024 -M realview-pbx-a9 -kernel $image >> ./log/$1genode_dump.txt"

#giving genode time to set things up
sleep $2

 

ping -c 1 $ip > /dev/null
if [ $? -eq 0 ]
then
	printf "%s" $1
else
	printf "%s" -1
fi
