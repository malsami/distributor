#!/bin/bash
user=bernhard
if [ $1 == 'rpi2' ];
then 
router_ip=10.200.32.252
elif [ $1 == 'rpi3'];
then
router_ip=10.200.32.253
else
router_ip=10.200.32.251
fi
command="/interface ethernet poe set poe-out=off $1$2"
ssh -l $user -i ~/.ssh/id_dsa $router_ip $command

