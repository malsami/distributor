import sys 
sys.path.append('../')
from taskgen.taskset import TaskSet
from taskgen.task import Task
from taskgen.blocks import *


def exampleTest():
    
    set = TaskSet([])
    
    # task01 = Task(hey.Value(1), period.Value(5000), priority.Value(0),{"numberofjobs" : 5}, {'caps':50})
    # set.append(task01)
    task02 = Task(pi.Value(2000), period.Value(2), priority.Value(0), {"numberofjobs" : 1000}, {'caps':50})
    set.append(task02)
    # task03 = Task(cond_42.Variants(5), period.Value(0), priority.Value(0), {'caps':50})
    # set.append(task03)
    # task04 = Task(cond_mod.Variants(5), period.Value(0), priority.Value(0), {'caps':50})
    # set.append(task04)
    # task05 = Task(linpack.Variants(5), period.Value(0), priority.Value(0), {'caps':50})
    #set.append(task05)

    return set





def example5():
    
    set = TaskSet([])
    
    task01 = Task(hey.Value(1), period.Value(5000), priority.HighRandom(),{"numberofjobs" : 5}, {'caps':50})
    set.append(task01)
    task02 = Task(pi.Variants(5), period.Value(0), priority.HighRandom(), {'caps':50})
    set.append(task02)
    task03 = Task(cond_42.Variants(5), period.Value(0), priority.HighRandom(), {'caps':50})
    set.append(task03)
    task04 = Task(cond_mod.Variants(5), period.Value(0), priority.HighRandom(), {'caps':50})
    set.append(task04)
    task05 = Task(linpack.Variants(5), period.Value(0), priority.HighRandom(), {'caps':50})
    set.append(task05)

    return set
