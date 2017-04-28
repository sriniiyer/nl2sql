from sets import Set
import json

def is_number(s):
    try:
        complex(s) # for int, long, float and complex
    except ValueError:
        return False
    return True

class Doc:
  def __init__(self, typ, rid, f):
    self.rid = rid
    self.f = f
    self.typ = typ

  def __eq__(self, other):
    return self.rid == other.rid

  def __hash__(self):
    return hash(self.rid)

  def __str__(self):
    print self.rid + ' ' + str(self.f)

def ooo(phrase, words):
  for i in range(0, len(words) - 1):
    p1 = phrase.find(words[i])
    p2 = phrase.find(words[i + 1])
    if p1 != -1 and p2 != -1 and p1 > p2:
      return True
  return False

class Index:

  def __init__(self, types, stop_word_file):
    self.d = {}
    self.types = types
    self.invTypes = {}
    for t in self.types:
      self.invTypes[self.types[t]] = t
    self.docs = {}
    self.stop_words = []
    for line in open(stop_word_file, 'r'):
      self.stop_words.append(line.strip())

    self.numDocs = 0

  def add(self, s, typ, rid, case=False):
    num_words = len(s.split())
    if num_words > 5:
      return

    if s.lower() in self.stop_words:
      return
    if not case:
      s = s.lower()
    # take care of quoting
    if is_number(s):
      self.docs[rid] = s
    else:
      self.docs[rid] = '"' + s + '"'

    for w in s.split():
      if w not in self.d:
        self.d[w] = []
      self.d[w].append(Doc(self.types[typ], rid, len(s.split()))) # Convert type to integer
    self.numDocs += 1


  def getKey(self, s, exact=False, case=False):

    res = None
    if not case:
      s = s.lower()

    words = s.split()
    for w in words:
      if w in self.d:
        if res == None:
          res = Set(self.d[w])
        else:
          res = res.intersection(self.d[w])
      elif exact:
        return (None, None) # No documents have this word and we want an exact match

    if res == None or not res:
      return (None, None)

    resList = []       # remove stuff that it in the wrong order
    for docum in res:
      phrase = self.docs[docum.rid]
      if not ooo(phrase, words):
        resList.append(docum)

    resList = sorted(resList, key=lambda x: x.f + (x.typ * 0.0001))
    
    fetchedDoc = self.docs[resList[0].rid]
    # Ordered by length
    if exact and len(s.split()) != len(fetchedDoc.split()):
      return (None, None)

    return ([self.docs[x.rid] for x in resList], [self.invTypes[x.typ] for x in resList])    