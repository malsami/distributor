#!/bin/bash


if [ -z $4 ]
then
end=$3;
else
end=$4;
fi

for i in $(seq $3 $end)
do
	if [ $1 == "2" ]
	then
		if [ $2 == "off" ]
  		then
			ssh bernhard@10.200.32.252  /interface ethernet poe set poe-out=off rpi2-$i
		fi
		if [ $2 == "on" ]
		then
 			ssh bernhard@10.200.32.252  /interface ethernet poe set poe-out=auto-on rpi2-$i
		fi
	fi
	if [ $1 == "3" ]
	then
		if [ $2 == "off" ]
		then
			ssh bernhard@10.200.32.253  	/interface ethernet poe set poe-out=off rpi3-$i
		fi
		if [ $2 == "on" ]
		then
	  		ssh bernhard@10.200.32.253  	/interface ethernet poe set poe-out=auto-on rpi3-$i
		fi
	fi
#  ssh bernhard@10.200.32.253  /interface ethernet set ether$i name=rpi3-$i
  echo $i;
done
