#!/bin/bash
user=robert
router_ip=10.200.32.251
command="/interface ethernet poe set poe-out=auto-on $1"
ssh -l $user -i ~/.ssh/id_dsa $router_ip $command

