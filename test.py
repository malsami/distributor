import sys
sys.path.append('../')
import logging
import time
from distributor.distributorClass import Distributor
from distributor.monitors.loggingMonitor import LoggingMonitor
from clean import clean_function
from taskgen.taskset import TaskSet
from taskgen.task import Task
from taskgen.blocks import *


def exampleTest():
    
    set = TaskSet([])
    
    task01 = Task(hey.Value(1), period.Value(5000), priority.Value(0), numberofjobs.Value(5), quota.Value(5), caps.Value(50))
    set.append(task01)
    task02 = Task(pi.Value(5), period.Value(0), priority.Value(0), quota.Value(5), {'caps':50})
    set.append(task02)
    task03 = Task(cond_42.Value(5), period.Value(0), priority.Value(0), quota.Value(5), {'caps':50})
    set.append(task03)
    task04 = Task(cond_mod.Value(5), period.Value(0), priority.Value(0), quota.Value(5), {'caps':50})
    set.append(task04)
    task05 = Task(linpack.Value(5), period.Value(0), priority.Value(0), quota.Value(5), {'caps':50})
    set.append(task05)

    return set


def example5():
    
    set = TaskSet([])
    
    task01 = Task(hey.Value(1), period.Value(5000), priority.Value(127), numberofjobs.Value(5), quota.Value(5), {'caps':50})
    set.append(task01)
    task02 = Task(pi.Variants(5), period.Value(0), priority.Value(2), quota.Value(5), {'caps':50})
    set.append(task02)
    task03 = Task(cond_42.Variants(5), period.Value(0), priority.Value(3), quota.Value(5), {'caps':50})
    set.append(task03)
    task04 = Task(cond_mod.Variants(5), period.Value(0), priority.Value(4), quota.Value(5), {'caps':50})
    set.append(task04)
    task05 = Task(linpack.Variants(5), period.Value(0), priority.Value(0), quota.Value(5), {'caps':50})
    set.append(task05)

    return set


def add_set(distributor, monitor):
	tset = exampleTest()
	distributor.add_job([tset], monitor)


sessions = ['QemuSession','PandaSession']
s_type = sessions[0]
mach = 1
mach_max = 1
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
