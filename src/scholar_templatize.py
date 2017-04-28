import gflags
FLAGS = gflags.FLAGS
import sys
import itertools
from Query import tokenizeQuery, tokenizeNL
from Schema import is_number
import json

def process(nl, sql):

  # first process SQL
  mapping = {}
  tokens = tokenizeQuery(sql)
  typNum = {}
  for i in range(0, len(tokens)):
    if tokens[i][0] == "'" or tokens[i][0] == '"' or is_number(tokens[i]):
      tab_found = False
      for j in range(1, i + 1):
        try:
          (tab, col) = tokens[i - j].split('.')
          tab_found = True
          break
        except:
          pass
      if not tab_found:
        continue

      typ = ""
      if col == "authorName":
        typ = "AUTHOR"
      elif col  == "datasetName":
        typ = "DATASET"
      elif col == "fieldName":
        typ = "FIELD"
      elif col  == "journalName":
        typ = "JOURNAL"
      elif col == "keyphraseName":
        typ = "KEYPHRASE"
      elif col  == "year":
        typ = "YEAR"
      elif col == "title":
        typ = "TITLE"
      elif col  == "venueName":
        typ = "VENUE"
      elif col  == "abstract":
        typ = "ABSTRACT"
      else:
        continue


      if tokens[i][0] == "'" or tokens[i][0] == '"':
        mapping[tokens[i][1:-1].lower()] = typ
      else:
        mapping[tokens[i].lower()] = typ

  # now process nl
  words = tokenizeNL(nl.lower())
  i = 0
  usedMapping = {}
  usedInvMapping = {} 
  while i < len(words):
    if i < len(words) - 2 and (words[i] + ' ' + words[i+1] + ' ' + words[i + 2]) in mapping: 
      phrase = words[i] + ' ' + words[i+1] + ' ' + words[i + 2]
      typ = ""
      if phrase in usedMapping:
        typ = usedMapping[phrase]
      else:
        typ = mapping[phrase]
        typNum[typ] = typNum.setdefault(typ, -1) + 1
        typ = typ + '@' + str(typNum[typ])
        usedMapping[phrase] = typ
        usedInvMapping[typ] = "'" + phrase + "'" if mapping[phrase] != 'YEAR' else phrase

      words[i] = typ
      words[i + 1] = ''
      words[i + 2] = ''
      i += 2
    elif i < len(words) - 1 and (words[i] + ' ' + words[i+1]) in mapping:
      typ = ""
      phrase = words[i] + ' ' + words[i+1]
      if phrase in usedMapping:
        typ = usedMapping[phrase]
      else:
        typ = mapping[phrase]
        typNum[typ] = typNum.setdefault(typ, -1) + 1
        typ = typ + '@' + str(typNum[typ])
        usedMapping[phrase] = typ
        usedInvMapping[typ] = "'" + phrase + "'" if mapping[phrase] != 'YEAR' else phrase

      words[i] = typ
      words[i + 1] = ''
      i += 1

    elif words[i] in mapping:
      typ = ""
      phrase = words[i]
      if phrase in usedMapping:
        typ = usedMapping[phrase]
      else:
        typ = mapping[phrase]
        typNum[typ] = typNum.setdefault(typ, -1) + 1
        typ = typ + '@' + str(typNum[typ])
        usedMapping[phrase] = typ
        usedInvMapping[typ] = "'" + phrase + "'" if mapping[phrase] != 'YEAR' else phrase

      words[i] = typ

    i += 1

  # substitute usedMapping in SQL
  for i in range(0, len(tokens)):
    if tokens[i][1:-1].lower() in usedMapping:
      tokens[i] = usedMapping[tokens[i][1:-1].lower()]

  return(' '.join(words), ' '.join(tokens), usedInvMapping)

def deanonymize(mp, sql):
  tokens = tokenizeQuery(sql)
  invMapping = json.loads(mp)
  for i in range(0, len(tokens)):
    if tokens[i] in invMapping:
      tokens[i] = invMapping[tokens[i]]
  return ' '.join(tokens)


def main(): 
  gflags.DEFINE_string("nlfile", "val_nl.txt", "file to be anonymised")
  gflags.DEFINE_string("sqlfile", "val_sql.txt", "sql file to be deanonymised")
  gflags.DEFINE_string("mapfile", "val_sql.txt", "sql file to be deanonymised")
  gflags.DEFINE_string("inst", "templatize", "sql file to be deanonymised")
  FLAGS(sys.argv)

  if FLAGS.inst == "templatize":
    fnl = open(FLAGS.nlfile + '.tem', 'w')
    mnl = open(FLAGS.nlfile + '.tem.map', 'w')
    fsql = open(FLAGS.sqlfile + '.tem', 'w')

    for (nl, sql) in itertools.izip(open(FLAGS.nlfile, 'r'), open(FLAGS.sqlfile, 'r')):
      (t_nl, t_sql, m_nl) = process(nl.strip(), sql.strip())
      fnl.write(t_nl + '\n')
      mnl.write(json.dumps(m_nl) + '\n')
      fsql.write(t_sql + '\n')

    fnl.close()
    fsql.close()
  elif FLAGS.inst == "deanonymize":
    fsql = open(FLAGS.sqlfile + '.deanon', 'w')

    for (mp, sql) in itertools.izip(open(FLAGS.mapfile, 'r'), open(FLAGS.sqlfile, 'r')):
      deanon = deanonymize(mp.strip(), sql.strip())
      fsql.write(deanon + '\n')
    fsql.close()

if __name__ == '__main__':
  main()