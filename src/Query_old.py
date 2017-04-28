
from copy import deepcopy
import re
from sets import Set
from Index import is_number
import json
import shlex
import itertools
from Timeout import TimeoutError
import _mysql_exceptions
from SqlMetric import runQueryWithConn

def tokenizeNL(s):
  s = re.sub('([,!?()])', r' \1 ', s)
  s = re.sub("'([a-zA-Z]+)\s", r" '\1 ", s) 
  s = re.sub("\.$", " .", s) 
  return s.split()

def tokenizeQuery(q):
  q = re.sub('([\\\,!?;+*<>()=/\-])', r' \1 ', q)
  try:
    tokens = shlex.split(q, posix=False)
  except:
    tokens = q.split()
  return tokens

class Query:
  def __init__(self, t, q, db=None, schemaObj=None):
    self.SEP = '$' 
    self.words = tokenizeNL(t)
    self.tokens = tokenizeQuery(q)

    self.operators = ['(', ')', ',', '=', '>', '<']
    self.db = db
    self.schemaObj = schemaObj

  def deanonymize(self, js):
    for i in range(0, len(self.tokens)):
      if self.tokens[i] in js:
        self.tokens[i] = js[self.tokens[i]]

  def run(self, timeout):
    self.lastQueryRan = ' '.join(self.tokens).replace(';', ' limit 100;')
    try:
      result = runQueryWithConn(self.lastQueryRan, timeout, self.db)
      self.ran = True

      self.table_map = {}
      self.newcols = []
      for f in result['fields']:
        col_q = f['name']
        tab_col = self.schemaObj.getNearestColumn(col_q)
        print(col_q)
        print(tab_col)
        if tab_col and tab_col[1].lower().endswith('id'):
          self.table_map.setdefault(tab_col[0], []).append((tab_col[1], col_q))
        else:
          self.newcols.append(col_q)

    except:
      print('didnt run')
      self.ran = False

  def getQuery(self):
    return ' '.join(self.tokens)


  def output(self, schema, db, paraphraser, data):
    self.tokensCopy = deepcopy(self.tokens)
    if not self.fillInJoins(schema):
      return
    nl = ' '.join(self.words).replace("_", " ").encode('ascii', 'replace')
    sql = ' '.join(self.tokens)
    sqlCopy = sql

    # Check if query runs
    for typ in sorted(schema.types, key=len, reverse=True):
      if typ == "INTEGER" or typ == "YEAR":
        # TODO: This is useless fot ATIS right now
        sqlCopy = sqlCopy.replace(typ + "@0", "10")
      else:
        sqlCopy = re.sub(typ + "@\d+", "\"moose\"", sqlCopy) #sqlCopy.replace(typ + "@0", "\"moose\"")
    # try to run sqlCopy
    try:
#       print sqlCopy
      res1 = runQueryWithConn(sqlCopy, 3000, db)
    except _mysql_exceptions.Warning:
      return
    except _mysql_exceptions.InterfaceError: #Timeout
      pass
    except Exception, e:
      print "ERROR:" + nl + self.SEP + sqlCopy + ' ' + str(e)
      import pdb
      pdb.set_trace()

    #self.outputParaphrases(nl, ' '.join(self.tokensCopy), paraphraser, data)
    self.outputParaphrases(nl, ' '.join(self.tokens), paraphraser, data)

  def outputParaphrases(self, nl, sql, paraphraser, data):
    pps = paraphraser.getParaphrases(nl.split())
    for p in pps:
      try:
        data.append((p, sql))
      except UnicodeDecodeError as ude: 
        pass



  @staticmethod
  def smartReplace(lst, frm, to, short):
    for i in range(0, len(lst)):
      if frm in lst[i] and (lst[i].count('{') > 1 or "*" in lst[i]):
        lst[i] = lst[i].replace(frm, to)
      elif frm == lst[i]:
        lst[i] = short
      elif frm in lst[i]:
        lst[i] = short

    return lst

  def apply(self, w, typeMap, schema):
    ret = []
    # First extract the first template in {}
    tplate = re.search("{.*?}", w).group(0)

    if tplate in typeMap:
      for v in typeMap[tplate]:
        qCopy = deepcopy(self)
        Query.smartReplace(qCopy.words, tplate, v, v)
        Query.smartReplace(qCopy.tokens, tplate, v, v)
        ret.append(qCopy)
    elif '{ENT' in tplate:
      for ent in schema.ents:
        # entUtt = schema.defaults[ent]["utt"]
        qCopy = deepcopy(self)
        Query.smartReplace(qCopy.words, tplate, ent, ent)
        Query.smartReplace(qCopy.tokens, tplate, ent, ent)
        ret.append(qCopy)
    elif '{COL' in tplate:
      # bug here. We only want to replace ENT1.
      ent = w.split('.')[0]
      for col in schema.ents[ent]:
        if schema.ents[ent][col]['index'] == True:
          qCopy = deepcopy(self)
          Query.smartReplace(qCopy.words, ent + "." + tplate, ent + "." + col, schema.ents[ent][col]['utt'])
          Query.smartReplace(qCopy.tokens, ent + "." + tplate, ent + "." + col, ent + "." + col)
          ret.append(qCopy)
    elif '{LITERAL' in tplate:
      # bug here. We only want to replace ENT1.
      ent = w.split('.')[0]
      col = w.split('.')[1]
      default_val = schema.ents[ent][col]['type'] + '@0'
      qCopy = deepcopy(self)
      Query.smartReplace(lst=qCopy.words, frm=ent + "." + col + "." + tplate, to=default_val, short=default_val)
      Query.smartReplace(qCopy.tokens, ent + "." + col + "." + tplate, default_val, default_val)
      ret.append(qCopy)
    elif '{DEF' in tplate:
      ent = w.split('.')[0]
      default_col = schema.defaults[ent]["col"] 
      qCopy = deepcopy(self)
      Query.smartReplace(qCopy.words, ent + "." + tplate, '', '') # Hack
      Query.smartReplace(qCopy.tokens, ent + "." + tplate, ent + "." + default_col, ent + "." + default_col)
      ret.append(qCopy)

    return ret

  @staticmethod
  def dfs_paths(graph, start, goal):
    stack = [(start, [start])]
    while stack:
      (vertex, path) = stack.pop()
      for next in set(graph[vertex].keys()) - set(path):
        if next == goal:
          yield path + [next]
        else:
          stack.append((next, path + [next]))

  def joinString(self, ent1, ent2, schema, fn):
    joins = []
    paths = [p for p in Query.dfs_paths(schema.links, ent1, ent2)]

    if len(paths) == 0:
      return None

    (minL, bestP) = (100000, None)
    for p in paths:
      if(len(p) < minL):
        minL = len(p)
        bestP = p

    # Add all tables in the path to the from clause
    # self.components['from']['cmp'].update(Set(bestP)) 

    for i in range(0, len(bestP) - 1):
      joins.append(bestP[i] + '.' + schema.links[bestP[i]][bestP[i + 1]] + ' = ' + bestP[i + 1] + '.' + schema.links[bestP[i + 1]][bestP[i]]     )

    joinString =  ' AND '.join(joins)

    return joinString if fn == "JOIN_WHERE" else ' , '.join(bestP)

  def fillInJoins(self, schema):
    tokens = self.tokens # self.components['where']['raw']
    for t in range(0, len(tokens)):
      if tokens[t] == 'JOIN_WHERE' or tokens[t] == "JOIN_FROM":
        ent1 = tokens[t + 2]
        ent2 = tokens[t + 4]
        tokens[t] = self.joinString(ent1, ent2, schema, tokens[t]) # join_from or join_where
        if tokens[t] is None:
          return None
        del tokens[t + 1:t + 6]
        return self.fillInJoins(schema)
    return True

if __name__=='__main__':
  import Schema
  schemaObj = Schema.Schema('s2/s2.json', 'stopwords.txt')
  q = Query('something', 'select paperId, count(1) from writes group by paperId;', 's2_small', schemaObj)
  q.run()
  print q.table_map
  res = q.runAllColumns()
  print res['default']
