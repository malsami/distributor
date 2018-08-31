import sys
sys.path.append('../')
import logging
import time
from distributor_service.distributor import Distributor
from distributor_service.malsamiTest import exampleTest, example5
from distributor_service.monitors.loggingMonitor import LoggingMonitor
from clean import clean_function

def add_set(distributor, monitor):
	tset = exampleTest()
	distributor.add_job(tset, monitor)


sessions = ['QemuSession','PandaSession']
s_type = sessions[1]
mach = 1
mach_max = 4
dis = Distributor(max_machine=1, max_allowed=mach_max, session_type=s_type, logging_level=logging.DEBUG, port=3001, startup_delay=20, set_tries=1, timeout=40)

logmon = LoggingMonitor()
for i in range(5):
	add_set(dis,logmon)
ext = ""
while ext == '':
	time.sleep(1)
	option = input("__________________________________________________\n(s)hut down machines || (a)dd taskset || (i)ncrease machines || (d)ecrease machines || e(x)it?\n")
	if option == "s":
		dis.kill_all_machines()
		print('shutting down all machine instances')
	elif option == "x":
		if s_type==sessions[0]:
			clean_function(mach_max)
		print('exiting')
		break
	elif option == 'a':
		add_set(dis,logmon)
		print('added set')
	elif option == "d":
		mach = max(1,mach-1)
		dis.set_max_machine_value(mach)
		print('new value: {}'.format(mach))
	elif option == "i":
		mach = min(mach+1, mach_max)
		dis.set_max_machine_value(mach)
		print('new value: {}'.format(mach))