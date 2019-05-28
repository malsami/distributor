#!/bin/bash
user=bernhard
if [[ $1 == 'rpi2-'* ]];
then
	echo 'went for rpi2'
	router_ip=10.200.32.252
elif [[ $1 == 'rpi3-'* ]];
then
	echo 'went for rpi3'
	router_ip=10.200.32.253
else
	echo 'still panda'
	router_ip=10.200.32.251
fi
command="/interface ethernet poe set poe-out=auto-on $1"
ssh $user@$router_ip $command

