#!/bin/bash

#Naked Variables 
mac=0a:06:00:00:00:$1
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

screen -dmS qemu$1 bash -c "qemu-system-arm -net tap,ifname=$tap,script=no,downscript=no -net nic,macaddr=$mac,model=lan9118 -nographic -smp 2 -m 1000 -M realview-pbx-a9 -kernel $image"
#getting pid of the screen, killing the screen will kill the qemu as well
pid="$(ps -ef | grep -ni -e "SCREEN -dmS qemu$1" | grep -v "grep" | awk '{print $2}')"

#giving genode time to set things up
sleep 20

 

ping -c 1 $ip > /dev/null
if [ $? -eq 0 ]
then
	printf "%s %s %s %s" $1 $pid $ip $mac 
else
	printf "%s %s %s %s" -1 $pid $ip $mac
fi
