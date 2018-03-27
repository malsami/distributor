from pynetlinux import *
from subprocess import *
import subprocess as sb
import sys
#import pexpect as p  
import random #For mac addressing
import os 

class Bridge(object):

	name = ""

	def __init__(self,name):
		self.name = name
		brctl.addbr(name)
		return None 




"""Deprecated"""
class Tap(ifconfig.Interface):

	name = ""

	def __init__(self):

		#self.name = name 
		#print("Built Tap object", 'name', 'blood')
		tap.Tap()
		return None 


    

    #def _create_mac_address(self, ipconfig.Interface):
#	pass

    #def call_hosts(self):
#	pass



"""Delete bridge from list of bridges"""

def delete_bridges(name):

	list_of_bridge = brctl.list_bridges()
	
	for br_name in list_of_bridge:
		
		if br_name == name:
			existing_bridge.delete()

	"""	
	existing_bridge = brctl.findbridge(name)

	if existing_bridge is not None:
	
		existing_bridge.delete()
"""
	#return None



def spawn_hosts_py(name):
	mac = ':'.join(("%12x" % random.randint(0, 0xFFFFFFFFFFFF))[i:i+2] for i in range(0, 12, 2))
	image = "ubuntu.img"
	
	cmd = "qemu-system-arm"
	cmd += " -net tap, ifname=%s,script=no,downscript=no" %name
	cmd += " -net nic,macaddr=%s" %mac 
	cmd += " -net nic,model=lan9118"
	cmd += " -nographic"
	cmd += " -m 1000"
	cmd += " -M realview-pbx-a9"
	cmd += " -kernel %s" %image

	cmd_two = "qemu-system-x86_64"
	print(cmd_two)
	child = p.spawn(cmd_two)
	#child.expect(['%',child.EOF])
	

	child.expect (['%',child.expect.EOF])                                     

	child.logfile = sys.stdout
	
	#print(sys.stdout)

def randomize_mac(): 
	pipe = Popen(["./rand_mac.sh"], stdout=PIPE, shell=True, stderr = PIPE)
	raw_output = pipe.communicate()
	mac = raw_output[0] #stdout is in 0 of tuple
	
	return mac

def get_qemu():
	print("Getting qemu")

def spawn_hosts(name):
	#Verbosity
	#sb.call("./qemu.sh")
	#sb.check_call(['./qemu.sh', name])
	#data = sys.stdin.read()
	#p = sb.Popen(["./qemu.sh"], shell=True)
	
	#mac = randomize_mac()
	#sb.check_call(['./qemu.sh',name, mac])
	mac = "00:50:56:f9:62:e8"

	checked_output = Popen(["./check_mac.sh",mac], stdout=PIPE, stderr=PIPE).communicate()[0]

	if(checked_output !=''):
		print("success")

	raw_output = Popen(["./qemu.sh", name, mac], stdout=PIPE, stderr=PIPE).communicate()[0]
	
#	std_out = raw_output.communicate()[0]
	print("raw_output: ", raw_output)
	#print("name: ", name)	
	#print("std_out: ", std_out)

	pidAndIP = raw_output.split()
	
	pid = pidAndIP[0]
	ip = pidAndIP[1]
	
	#print("pid: %s, ip: %s",pid,ip)	
	#print("Ending bash script///Back to python")
	#print(p.communicate())
	#print(p.communicate())







if __name__ == '__main__':
		
		
		#spawn_hosts(tap_one.name)

		#active_host = Popen(["./check_mac.sh",mac], stdout=PIPE, stderr=PIPE).communicate()[0]

		mac = randomize_mac()
		print(mac)
		
		"""for arg in sys.argv[2]:
			br.append(arg)



		if(sys.argv[1] == "delete"):
			print("Deleting...")
			delete_bridges(br)

		

	



		#else build bridges 
		bridge = Bridge(sys.argv[1])

			#Adding Tap inteface
		my_tap = bridge.Tap("myTap")

		my_tap.up() #Set interface to up 
		bridge.addif(my_tap.name)

		#if(brctl.findbridge(bridge.name) != None):
		#	print("Success")
		
		#br = brctl.findbridge("theBridge")

		#br.delete()

		#print("Bridge created")

		if(sys.argv[1] == "delete"):
			
		#tap = bridge.Tap("myTap")


		"""
