
class TimeoutError(Exception):
  def __init__(self):
    Exception.__init__(self,"well, it timed out") 

