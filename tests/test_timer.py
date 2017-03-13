from pychinadns.timer import TimerManager
import time

tm = TimerManager()

def func1():
    print "%f func1" %(time.time())

def func2():
    print "%f func2" %(time.time())

def func3():
    print "%f func3" %(time.time())

tm.AddTimer(3, func3)
tm.AddTimer(2, func2)
tm.AddTimer(1, func1)

while True:
    tm.CheckTimer()
    time.sleep(1)
