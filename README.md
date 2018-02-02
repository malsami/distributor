###Here we will implement the distributor as a service.
The service will be running in the background, holding an instance of the distributor.

The service will provide an interface for the following commands:

* _service\_start_
* _service\_stop_
* _service\_status_
* _add\_taskset_

 expects a taskset as provided by the [taskgen module]()

* _check\_state_
* _get\_max\_machine\_value_

 returns the current max\_machine\_value

* _change\_max\_machine\_value_

 expects a positive integer

The distributor is started upon starting the service and is running _idle_ in the background. 
At initial startup of the distributor a network bridge is created.(including a possible cleanup)
If the _max\_machine\_value_ is not set manually, the default value will be 'TODO'.
As soon as a taskset is provided, the distributor switches into the _running_ state.
Tasksets can only be submitted via the service.
In the _running_ state, the Distributor will start up to _max\_machine\_value_ threads.
Each thread is spawning a Qemu instance and creates a session to connect to it.

After exhausting all submitted tasksets the distributor falls back into the 'idle' state.
The machines are killed and the threads are closed untill a new taskset is submitted

####Additional information:

 The bridge is only removed upon closing the distributor.

 Changing the _max\_machine\_value_ while the distributor is _running_ results in an adjustment of the number of running machines.

 Submiting tasksets for processing always (_idle_ / _running_) places them into a queue of tasksets to be processed.
(maybe it should also be possible to abort submitted tasksets)


