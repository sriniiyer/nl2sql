import collections
import math
import sys
import gflags
FLAGS = gflags.FLAGS
import itertools
from Query import tokenizeNL

class Document:

  def __init__(self, sql, nl):
    self.nl = nl
    self.sql = sql
    self.nlTokens = tokenizeNL(nl)
    self.tf = self.getTf()

  def getTf(self):
    tf = collections.Counter()
    for tok in self.nlTokens:
      tf[tok] += 1
    for tok in tf:
      tf[tok] = tf[tok] * 1.0 / len(self.nlTokens)
    return tf

  def __str__(self):
    return self.nl

  def computeTfidf(self, idf, numDocs):
    self.tfidf = collections.Counter()
    self.norm = 0
    for tok in self.tf:
      if tok in idf:
        self.tfidf[tok] += self.tf[tok] * (1 + math.log(numDocs * 1.0 / len(idf[tok])))
        self.norm += self.tfidf[tok] * self.tfidf[tok]
    self.norm = math.sqrt(self.norm)

  def getTfIdfScore(self, testDoc):
    dotScore = 0.0
    selfNorm = 0.0

    for tok in testDoc.tfidf:
      if tok in self.tfidf:
        dotScore += testDoc.tfidf[tok] * self.tfidf[tok]

    return dotScore  / self.norm / testDoc.norm 

class DocumentList():
  def __init__(self, corpus):
    self.idf = {}
    self.numDocs = 0
    self.documents = {}
    rid = 1
    for (nl, sql) in corpus:
      doc = Document(sql, nl)
      self.documents[rid] = doc
      self.storeIdf(doc.nlTokens, rid)
      self.numDocs += 1
      rid += 1
    
  def computeTfidf(self):
    for d in self.documents:
      self.documents[d].computeTfidf(self.idf, self.numDocs)

  def test(self, nl):
    score = 0.0

    testDoc = Document('None', nl)
    testDoc.computeTfidf(self.idf, self.numDocs)
    closestDoc = self.getClosest(testDoc)
    return (closestDoc.nl, closestDoc.sql)

  def storeIdf(self, nlTokens, rid):
    for tok in nlTokens:
      if tok not in self.idf:
        self.idf[tok] = set()
      self.idf[tok].add(rid)

  def getClosest(self, testDoc):
    maxScore = -1
    maxDocument = None

    # Instead of checking all documents, we only want to check documents with
    # common words
    documents = set()
    for tok in testDoc.tf:
      if tok in self.idf:
        documents.update(self.idf[tok])

    for t in documents:
      score = self.documents[t].getTfIdfScore(testDoc)
      if score > maxScore: # Dont accidentally return the same document
        maxScore = score
        maxDocument = self.documents[t]

    return maxDocument

if __name__ == '__main__':
  gflags.DEFINE_string("nl", "something", "file containing trace")
  gflags.DEFINE_string("sql", "something", "file containing trace")
  gflags.DEFINE_string("testnl", "something", "file containing trace")

  FLAGS(sys.argv)

  corpus = []
  for (nl, sql) in itertools.izip(open(FLAGS.nl, 'r'), open(FLAGS.sql, 'r')):
    corpus.append((nl.strip(), sql.strip()))

  dlist = DocumentList(corpus)
  dlist.computeTfidf()

  for nl in open(FLAGS.testnl, 'r'):
    (closest_nl, closest_sql) = dlist.test(nl.strip())
    print closest_sql
