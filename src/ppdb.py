import random
import copy
import sys

class PPDB:

  def __init__(self, filename, scale):

    self.scale = scale
    self.forbidden = ["and", "all", "there", "COUNTRY", "is", "LAKE", "as", "are", "in", "MOUNTAIN", "return", "find", "what", "RIVER", "show", "when", "their", "which", "INTEGER", "many", "get", "whose", "number", "STATE", "CAPITAL", "with", "me", "CITY", "give", "name", "of", "?", "how", "the", "where", "fetch", "POINT"]

    if self.scale > 0: # No need if ppscale is 0
      self.paraphrases = {}
      self.position = {}
      for line in open(filename, 'r'):
        cols = line.strip().split(' ||| ')
        lst = self.paraphrases.setdefault(cols[1], [])
        if cols[2] not in lst:
          lst.append(cols[2])

      # shuffle all paraphrases
      avg = 0.0
      mx = 0.0
      for key in self.paraphrases:
        if len(self.paraphrases[key]) > mx:
          mx = len(self.paraphrases[key])
        avg += len(self.paraphrases[key])
        random.shuffle(self.paraphrases[key])

      avg /= len(self.paraphrases)
     
      # print out some stats
      sys.stderr.write('Paraphrases loaded!\n')
      sys.stderr.write('Avg paraphrases ' + str(avg) + '\n')
      sys.stderr.write('Max paraphrases ' + str(mx) + '\n')
      sys.stderr.write('Total paraphrase keys ' + str(len(self.paraphrases)) + '\n')


  def getNumCandidates(self, tokens):
    ret = 0
    for t in tokens:
      if t not in self.forbidden and t in self.paraphrases:
        ret += 1
    return ret

  def getRandomParaphrase(self, tokens):

    # pick random position
    numCand = self.getNumCandidates(tokens)
    if numCand == 0:
      return None 
    # print str(numCand) + ' candidates' 
    pos = random.randint(0, numCand - 1)
    j = -1
    for i in range(0, len(tokens)):
      if tokens[i] not in self.forbidden and tokens[i] in self.paraphrases:
        j += 1
      if j == pos:
        listPos = self.position.setdefault(tokens[i], 0)
        try:
          self.position[tokens[i]] = (self.position[tokens[i]] + 1) % len(self.paraphrases[tokens[i]])
        except:
          import pdb
          pdb.set_trace()
        tokens[i] = self.paraphrases[tokens[i]][listPos]
        break

    return tokens

  def getParaphrases(self, toks):
    pps = [' '.join(toks)]
    for i in range(0, self.scale):
      tokens = copy.deepcopy(toks)
      pp = self.getRandomParaphrase(tokens)
      if pp:
        pps.append(' '.join(pp))
    return pps

if __name__ == '__main__':
  p = PPDB('./ppdb/ppdb-1.0-xxl-lexical', 20)
  toks = ['get', 'me', 'the', 'size', 'of', 'california']
  print p.getParaphrases(toks)