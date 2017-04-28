import MySQLdb
import warnings
import sys
import itertools
from sets import Set
import multiprocessing
from s2s.data.Timeout import TimeoutError
import re
import _mysql_exceptions
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def runQuery(q, timeout, dbconn):
  q = q.replace(' (','(').replace('< =', '<=').replace('> =', '>=').replace('< >', '<>').replace('! =', '!=')
  q = re.sub('^SELECT ','SELECT /*+ MAX_EXECUTION_TIME(' + str(timeout) + ') */ ', q)
  q = re.sub('^select ','SELECT /*+ MAX_EXECUTION_TIME(' + str(timeout)+ ') */ ', q)
  cu = dbconn.cursor()
  cu.execute(q)
  result = {}
  result['tuples'] = cu.fetchall()
  result['status'] = True
  result['row_count'] = cu.rowcount
  if cu.description:
    result['fields'] = [
        {'name': col[0], 'type': col[1]} for col in cu.description]
  cu.close()
  return result

def runQueryWithConn(q, timeout, dbName, host, user, passwd):
  warnings.filterwarnings('error', category=MySQLdb.Warning)
  dbconn = MySQLdb.connect(
    host=host,
    user=user,
    passwd=passwd,
    db=dbName
  )
  try:
    res = runQuery(q, timeout, dbconn)
  except Exception, e:
    dbconn.close()
    raise e
  dbconn.close()
  return res

def compute(dbName, num, gold, q1, host, user, passwd):

  dbconn = MySQLdb.connect(
    host=host,
    user=user,
    passwd=passwd,
    db=dbName
  )

  warnings.filterwarnings('ignore', category=MySQLdb.Warning)

  # Run predicted query
  try:
    res1 = runQuery(q1, 3000, dbconn)
    res1 = res1['tuples']
  except _mysql_exceptions.ProgrammingError:
    res1 = []
  except _mysql_exceptions.InterfaceError:
    res1 = []
  except _mysql_exceptions.OperationalError:
    res1 = []
  except _mysql_exceptions.NotSupportedError:
    res1 = []

  # Run gold query
  try:
    res2 = runQuery(gold, 3000, dbconn)
    res2 = res2['tuples']
  except _mysql_exceptions.ProgrammingError:
    import pdb
    pdb.set_trace()
    raise ValueError('Gold Query does not run')
  except _mysql_exceptions.InterfaceError:
    res2 = []
    
  dbconn.close()

  res1_set = Set()
  for x in res1:
    res1_set.add(x)

  res2_set = Set()
  for x in res2:
    res2_set.add(x)

  if res1_set != res2_set:
    return (0, 1, 0, num, gold, q1)
  return (1, 1, 0, num, gold, q1)


class SqlMetric:

  def __init__(self, db, debug, debugFile, warn):
    self.dbName = db
    self.db = None
    self.debug = debug
    self.debugFile = open(debugFile, 'w') if debugFile != '' else None

  def computeFromFiles(self, goldFile, methodFile, host, user, passwd):
    warnings.filterwarnings('ignore', category=MySQLdb.Warning)
    pool = ThreadPoolExecutor(10)
    score = 0
    num = 0.0
    goldFile = open(goldFile, 'r')
    methodFile = open(methodFile, 'r')
    futures = []
    for g, m in itertools.izip(goldFile, methodFile):
      futures.append(pool.submit(compute, self.dbName, num, g.strip(), m.strip(), host, user, passwd))
      num += 1

    print(num)
    for x in as_completed(futures):
      (s, success, err, n, g, m) = x.result()
      if self.debugFile:
        self.debugFile.write(str(n + 1) + '\t' + g + '\t' + m + '\t' + str("W" if s == 0 else "R" ) + '\t' + str("" if success == 1 else "F") + '\n')
      score += s

    if self.debugFile:
      self.debugFile.close()
    return (score, num, score * 100.0 / num)

  def computeFromMaps(self, goldMap, methodMap):
    score = 0
    num = 0.0

    for key in goldMap:
      if key in methodMap:
          
        if self.debug:
          sys.stdout.write(str(key) + ' ')
        (s, success) = self.compute(goldMap[key][0], methodMap[key][0])
        if self.debugFile:
          self.debugFile.write(str(key) + '\t' + goldMap[key][0] + '\t' + methodMap[key][0] + '\t' + str("W" if s == 0 else "R" ) + '\t' + str("" if success == 1 else "F") + '\n')
        score += s
        num += 1

    if self.debugFile:
      self.debugFile.close()
    return (score, num, score * 100.0 / num)

if __name__ == '__main__':
  b = SqlMetric('atis', False, '', 'error')
  b.runQuery('SELECT sum(from_airport) from flight;')
