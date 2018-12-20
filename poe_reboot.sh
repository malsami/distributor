#!/bin/bash
user=robert
router_ip=10.200.32.137
command="/interface ethernet poe power-cycle $1"
ssh -l $user -i ~/.ssh/id_dsa $router_ip $command
