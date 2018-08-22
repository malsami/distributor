import sys
sys.path.append('../')
import logging
import time
from distributor_service.distributor import Distributor
from distributor_service.malsamiTest import exampleTest, example5
from distributor_service.monitors.loggingMonitor import LoggingMonitor

dis = Distributor(logging_level=logging.INFO)
mach = 2
mach_max = 8
dis.set_max_machine_value(1)
logmon = LoggingMonitor()
for i in range(5):
	tset = exampleTest()
	dis.add_job(tset,logmon)
ext = ""
while ext == '':
	time.sleep(1)
	option = input("(k)ill machines or e(x)it?\n")
	if option == "k":
		dis.kill_all_machines()
	elif option == "x":
		break
	elif option == "l":
		mach = max(1,mach-1)
		dis.set_max_machine_value(mach)
	elif option == "m":
		mach = min(mach+1, mach_max)
		dis.set_max_machine_value(mach)