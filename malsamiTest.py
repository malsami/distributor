import sys 
sys.path.append('../')
from taskgen.taskset import TaskSet
from taskgen.task import Task
from taskgen.blocks import *

class SetForRobert(TaskSet):

    #just commt out if it'S to much or reduce numberOfVariants
    # Hey           =     1
    # Pi            =    10
    # cond_42       =    10
    # cond_mod      =    10
    # linpack       =    10
    # ---------------------
    # 1^10^10^10^10 = 10000

    #for even more Tasksets replace HighRandom() with Variants() then not only 1 Value is used but all possible values (at period and at priority possible)
    #or add even more Tasks

    def __init__(self):
        numberOfVariants = 10
        super().__init__()
        task01 = Task(hey.HelloWorld, period.HighRandom(), priority.HighRandom())
        self.append(task01)
        task02 = Task(pi.Variants(numberOfVariants), period.HighRandom(), priority.HighRandom())
        self.append(task02)
        task03 = Task(cond_42.Variants(numberOfVariants), period.HighRandom(), priority.HighRandom())
        self.append(task03)
        task04 = Task(cond_mod.Variants(numberOfVariants), period.HighRandom(), priority.HighRandom())
        self.append(task03)
        task05 = Task(linpack.Variants(numberOfVariants), period.HighRandom(), priority.HighRandom())
        self.append(task03)
