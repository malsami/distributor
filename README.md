### The Distributor
The Distributor component in [distributor.py] manages a certain (predefined) number of Machine instances. It also takes care of data that was provided to the Distributor for execution And provides it to the Machine instances.

The Disttributor provides the following options via its init().
If no values are set, the init is called as follows:
```python
init(max_machine=1, max_allowed=42, session_type="QemuSession", logging_level=logging.DEBUG, bridge='br0', port=3001, startup_delay=20, set_tries=1, timeout=40)
```
## variable Values
* max\_machine 
  determines the maximal number of machines, which can be started in this Distributor instance
* session\_type 
  is used to determine the session type to fit the target hardware setup, only accepts sessions defined in [sessions/genode.py] (this is defined in line 47 in [distributor.py])
* logging_level 
  takes a logging level like logging.DEBUG or logging.CRITICAL
* startup\_delay 
  defines how long a session waits to establsh a connection to Genode after starting a qemu instance or another hardware board
* set_tries
  defines the maximum amount of times a taskset is tried after it had to be aborted due to Genode not responding anymore
* timeout
  defines a time in seconds of no new message from Genode after which the session component belives Genode to be dead

## not to be changed via at init
* max\_allowed 
  determines a maximum value, currently set to 42, this limit is due to the limited entries in the dhcp configuration used in our setup
* bridge 
  defines the name of the virtual network bridge used with the quemu instances
* port 
  defines the port for the connection with Genode

## Methods for use
* get\_max\_machine\_value()
  this returns the current value of max\_machine
* set\_max\_machine\_value(new\_value)
  sets the current max\_machine\_value to max(new\_value, max\_allowed)
* kill\_all\_machines()
  hard kill of all running Machine instances
* reboot\_genode()
  sends signal so reboot Genode after finishing the currently executed taskset
* shut\_down\_all\_machines()
  lets Machines finish their current taskset and then they shut down
* add\_jobs(tasksetList, monitor, offset)
  accepts a list of TaskSet (from the taskgen module) instances and some monitor implementing monitor.AbstractMonitor.  In addition an offset can be provided if the first 'offset' TaskSet elements should be discarded
  

