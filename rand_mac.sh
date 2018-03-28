#!/bin/bash

#0m is for Project malsami, 
mac=$(hexdump -vn1 -e '/1 "0a:06:00:00:00"' -e '/1 ":%02x"' -e '"\n"' /dev/urandom)

#echo $mac
printf "%s" $mac 