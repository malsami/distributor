#!/bin/bash

#Naked Variables 
tap="$1"
mac="$2"
image="../build/genode-focnados_pbxa9/var/run/dom0-HW/image.elf" #input genode image

#echo $tap  
#echo "executed qemu script"


#mac="$(hexdump -vn3 -e '/3 "52:54:00"' -e '/1 ":%02x"' -e '"\n"' /dev/urandom)"

#echo "Created random mac address"
#echo $qemu_ip
#echo "Creating pid"

#pid=$!

#echo $pid

#echo "Execuring Qemu Script"


qemu-system-x86_64 -net tap,ifname=$tap,script=no,downscript=no \
		            -net nic,macaddr=$mac \
		            -net nic,model=lan9118 \
		            -nographic \
		            -smp 2 \
		            -m 1000 \
		            -M realview-pbx-a9 \
		            -kernel $image &
    pid=$!

#echo "Executing Done" 



 
qemu_ip=$(arp -n | grep -w -i $mac |awk '{print $1}')

printf "%s %s %s" $pid $qemu_ip $mac 
#>&2 echo $pid 