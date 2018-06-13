#!/bin/bash
pid="$(screen -ls | grep -ni -e "qemu$1\b" | grep -v "grep" | awk '{print $2}')"
echo $pid