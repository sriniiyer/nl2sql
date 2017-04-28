import shlex
from pattern.en import pluralize, singularize
from Index import Index, is_number
import MySQLdb
import cPickle as pickle
import commentjson
import gflags
import sys
import re
import subprocess
import tempfile
import os

FLAGS = gflags.FLAGS

def applyOperation(toks, start, end, sub):
  toks[start] = sub
  for i in range(start + 1, end):
    toks[i] = ''

class Schema:

  def __init__(self, filename, stopfile):
    self.schema = commentjson.loads(open(filename, 'r').read())

    #just convenience
    self.ents = self.schema['ents']
    self.types= self.schema['types']
    self.ind = Index(self.types, stopfile)
    self.indexFile = 'index'
    if 'links' in self.schema:
      self.defaults = self.schema['defaults']
      self.links = self.schema['links']

  def isTable(self, t):
    return t.lower() in self.ents

  def normalizeTables(self, words):
    for i in range(0, len(words)):
      singular = singularize(words[i].lower())
      if self.isTable(singular):
        words[i] = singular

  def allInitCaps(self, s):
    return all(word[0].isupper() or is_number(word) for word in s.split())

  def getAnonymizationStructure(self, words):
    # deal with first word
    if singularize(words[0].lower()) in self.ind.stop_words or singularize(words[0].lower()) in self.ents:
      words[0] = words[0].lower()
    self.normalizeTables(words)

    spans = {}
    i = 0
    while i < len(words):
      for w in range(3, 0, -1):
        at_most_2 = {}
        span = ' '.join(words[i:i+w]).replace('#', ' ')
        exact=True
        if self.allInitCaps(span):
          exact = False
        if not self.allInitCaps(span):
          continue
        (docs, typs) = self.ind.getKey(span, exact=exact, case=(len(span) <=2) )
        if docs:
          spans[i] = {'width' : w, 'docs' : [], 'types' : []}
          for j in range(0, len(docs)):
            if at_most_2.setdefault(typs[j], 0) < 2: #  typs[j] not in spans[i]['types']:
              spans[i]['types'].append(typs[j])
              spans[i]['docs'].append(docs[j])
              at_most_2[typs[j]] += 1

          i = i + w - 1 # we have finished the span
          break
      i += 1
    return spans

  def buildIndex(self, filename, db, host, user, passwd):

    db = MySQLdb.connect(host=host, user=user, passwd=passwd, db=db)
    cursor = db.cursor()

    i = 0 # i is just the document number
    for ent in self.ents:
      for col in self.ents[ent]:
        if self.ents[ent][col]['index'] == True:
          cursor.execute('select distinct ' + col + ' from ' + ent)
          print cursor._last_executed
          rows = cursor.fetchall()
          for r in rows:
            if r[0] != None:
              val = r[0]
              val = str(val).encode('ascii', 'replace')
              self.ind.add(val, self.ents[ent][col]['type'], str(i), case=(len(val) <= 2))
              i += 1

    cursor.close()
    with open(filename, 'wb') as handle:
      pickle.dump(self.ind, handle)  