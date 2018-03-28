from example import Hey0TaskSet
from monitors.loggingMonitor import LoggingMonitor
from distributor import Distributor

t = Hey0TaskSet()
lm = LoggingMonitor()
dist = Distributor()
print("Initialized Distributor")
#dist.set_max_machine_value(2)
dist.add_job(t,lm)

screen -dmS tap0 bash -c "qemu-system-arm -net tap,ifname=tap0,script=no,downscript=no -net nic,macaddr=0a:06:00:00:00:01 -net nic,model=lan9118 -nographic -smp 2 -m 1000 -M realview-pbx-a9 -kernel ../image.elf"
