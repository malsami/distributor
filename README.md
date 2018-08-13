### The Distributor as a Service.
The service will be running in the background, holding an instance of the distributor.

The service will provide an interface for the following commands:

* _service\_start_
* _service\_stop_
* _service\_status_
* _add\_job_

  expects a taskset and a monitor as defined by the [taskgen module]()

* _check\_state_
* _get\_max\_machine\_value_

  returns the current max\_machine\_value

* _change\_max\_machine\_value_

  expects a positive integer

The distributor is instantiated upon starting the service and is running _idle_ in the background. 
At initial startup of the distributor a network bridge with the name **br0** is created.(including a possible cleanup of an existing bridge of the same name)
If the _max\_machine\_value_ is not set manually, the default value will be **1**.
As soon as a taskset is provided, the distributor switches into the _running_ state.
Tasksets can only be submitted via the service.
In the _running_ state, the Distributor will start up to _max\_machine\_value_ threads.
Each thread is spawning a Qemu instance and creates a session to connect to it.

After exhausting all tasksets in the submitted jobs the distributor falls back into the 'idle' state.
The machines are killed and the threads are closed untill a new job is submitted

#### Additional information:

 The bridge is not yet removed upon closing the distributor. TODO

 Changing the _max\_machine\_value_ while the distributor is _running_ results in an adjustment of the number of running machines.

 Submiting a job for processing always (_idle_ / _running_) places it into a queue of jobs to be processed.
(maybe it should also be possible to abort submitted jobs)




NETWORK BRIDGEING WITH DHCP : 


On host machine, add these lines to /etc/network/interface

auto br0
iface br0 inet dhcp
bridge_ports eth0
bridge_stp off
bridge_maxwait 0
bridge_fd 0

Also add new dhcp.conf file. 