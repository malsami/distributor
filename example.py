from taskgen.task import Task
from taskgen.taskset import TaskSet, BlockTaskSet
from taskgen.blocks import *


class Hey0TaskSet(TaskSet):
    """Static task with the `hey` binary. 
    
    It is possible to create a task from a dictionary. All values from the dict
    are mapped directly to a xml represenation.
    """
    def __init__(self):
        super().__init__()
        task = Task({
            # general
            "id" : 1,
            "executiontime" : 99999999,
            "criticaltime" : 0,
            # binary
            "quota" : "1M",
            "pkg" : "hey",
            "config" : {},
            # frequency
            "period" : 2000,
            "numberofjobs" : 0,
            # schedular
            "priority" : 10,
        })
        self.append(task)


class Hey1TaskSet(TaskSet):
    """Static task with the `hey` binary.
    
    Attributes, defined in `taskgen.attrs` simplifies the task
    creation. Attributes are dicts with predefined values.
    """

    def __init__(self):
        super().__init__()
        task = Task(
            hey.HelloWorld,  # fills `pkg`, `config`, `executiontime` and `quota`
            priority.Custom(100), # fills `priority`
            period.Custom(5) # fills period
        )
        self.append(task)
        
class Hey2TaskSet(BlockTaskSet):
    """Static task with the `hey` binary.
    
    If you want to create specific tasksets with the predefinied attributes,
    `BlockTaskSet` might be helpful.
    """

    def __init__(self):
        super().__init__(
            hey.HelloWorld,
            priority.Custom(100),
            period.Custom(5)
        )


class Hey3TaskSet(BlockTaskSet):
    """Two static tasks with the `hey` binary.
    
    `BlockTaskSet` allows to combinate building blocks of attributes. This
    example creates 2 `hey`-tasks with various period.

    """

    def __init__(self):
        super().__init__(
            hey.HelloWorld,
            priority.Custom(100),
            [period.Custom(5), period.Custom(10)]
        )

        
class Hey4TaskSet(BlockTaskSet):
    """Four static tasks with the `hey` binary, various periods and priorities.
    
    `BlockTaskSet` allows to combinate building blocks of attributes. This
    example creates 4 `hey`-tasks with various period and priorities.

    """

    def __init__(self):
        super().__init__(
            hey.HelloWorld,
            [priority.Custom(100), priority.Custom(100)],
            [period.Custom(5), period.Custom(10)]
        )

        
class Hey5TaskSet(BlockTaskSet):
    """One task with the `hey` binary and random priority.
    
    `BlockTaskSet` allows to combinate building blocks with random
    attributes. Random blocks are function, which returns randomly generated
    dicts.

    """

    def __init__(self):
        super().__init__(
            hey.HelloWorld,
            priority.Random,
            period.Custom(5)
        )

class Hey6TaskSet(BlockTaskSet):
    """One task with the `hey` binary and all priority variants
    
    `BlockTaskSet` allows to create variants of building blocks. Variant blocks
    are function, which returns a dicts with value ranges. This example creates
    a taskset with one task and 128 variants, which all differ in the priority.

    """

    def __init__(self):
        super().__init__(
            hey.HelloWorld,
            priority.Variants,
            period.Custom(5)
        )

class Hey7TaskSet(BlockTaskSet):
    """2 tasks with the `hey` binary, random period and all priority variants (2^128 variants).
    """

    def __init__(self):
        super().__init__(
            [hey.HelloWorld, hey.HelloWorld], # 2 tasks
            priority.Variants,  # 128 priority variants
            period.Random  #1-20 seconds periods
        )


class Hey8TaskSet(TaskSet):
    """10 static tasks with the `hey` binary.
    """

    def __init__(self):
        super().__init__()

        for x in range(10):
            task = Task(
                hey.HelloWorld,
                priority.Custom(100),
                period.Custom(5)
            )
            self.append(task)

            
class Hey9TaskSet(TaskSet):
    """10 tasks with the `hey` binary and random priorities.
    """

    def __init__(self):
        super().__init__()

        for x in range(10):
            task = Task(
                hey.HelloWorld,
                priority.Random,
                period.Custom(5)
            )
            self.append(task)

