#!/bin/bash
#call with ./clean_id.sh id pid
sudo kill -9 $2
sudo ip link delete tap$1