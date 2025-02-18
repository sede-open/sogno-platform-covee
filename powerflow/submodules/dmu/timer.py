import threading
import time
from typing import Callable

class Timer(threading.Thread):
    def __init__(self, interval: float, func: Callable):
        self.interval = interval
        self._func = func
        self._timer_in_use = threading.Event()
        self._timer_runs = threading.Event() # used to pause and start the timer
        self._timer_runs.set()
        self.created = True 
        super().__init__()
        
    
    def run(self):
        while self._timer_in_use.is_set():
            self._timer_runs.wait()
            while(self._timer_runs.is_set()):
                self._func()
                time.sleep(self.interval)
    
    
    def __exit__(self):
        def noop():
            pass
        self._func = noop
        self.interval = 0.0001
        self._timer_in_use.clear()
        self._timer_runs.set() # if we are already waiting. we must cycle through one run
        self.stop()
        
    
    def stop(self):
        """Stops a timer after the before the next timer invocation. May take up to 1 interval time.
            To start a new timer reuse start function.
        """
        self._timer_runs.clear()
        
        
    def start(self) -> None:
        """Creates a new timer. If the timer has already been startet this is a noop.

        Returns:
            None: 
        """
        if not self.created:
            return super().start()
            
        self._timer_runs.set()
