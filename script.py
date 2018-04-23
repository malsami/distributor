#this is some code for testing purposes

from example import Hey0TaskSet
from monitors.loggingMonitor import LoggingMonitor
from distributor import Distributor

t = Hey0TaskSet()
lm = LoggingMonitor()
dist = Distributor()
dist.add_job(t,lm)

print("Initialized Distributor")
#dist.set_max_machine_value(2)
dist.add_job(t,lm)

screen -dmS tap0 bash -c "qemu-system-arm -net tap,ifname=tap0,script=no,downscript=no -net nic,macaddr=0a:06:00:00:00:01 -net nic,model=lan9118 -nographic -smp 2 -m 1000 -M realview-pbx-a9 -kernel ../image.elf"


#Should be done after bridge creation
#sudo ip addr add 10.200.45.1/24 dev br0
from xml.dom.minidom import parseString
import dicttoxml
from example import Hey0TaskSet

t = Hey0TaskSet()
it = t.variants()
elem = it.__next__()
print(elem.description())

list_item_to_name = lambda x : "periodictask"
description = dicttoxml.dicttoxml(elem.description(), attr_type=False, root=False, item_func=list_item_to_name)

print(parseString(description).toprettyxml())
print(description)
print(str(description, "ascii"))
