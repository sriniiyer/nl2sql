import gflags
FLAGS = gflags.FLAGS
import sys
import itertools
from Query import tokenizeQuery, tokenizeNL
import json

def process(nl, sql):

  # first process SQL
  mapping = {}
  invMapping = {}
  tokens = tokenizeQuery(sql)
  typNum = {}
  for i in range(0, len(tokens)):
    if tokens[i][0] == "'" or tokens[i][0] == '"':
      try:
        if tokens[i - 1] == "=" or tokens[i - 1] == "LIKE":
          (tab, col) = tokens[i - 2].split('.')
        else:
          (tab, col) = tokens[i - 3].split('.')
      except:
        import pdb
        pdb.set_trace()
      typ = ""
      if col in ["state_name", "border", "traverse"]:
        typ = "STATE"
      elif col  == "city_name" or col == "capital":
        typ = "CITY"
      elif col  == "lowest_point" or col == "highest_point":
        typ = "POINT"
      elif col  == "lake_name":
        typ = "LAKE"
      elif col  == "mountain_name":
        typ = "MOUNTAIN"
      elif col  == "river_name":
        typ = "RIVER"

      mapping[tokens[i][1:-1]] = typ
      
  # now process nl
  words = tokenizeNL(nl)
  i = 0
  usedInvMapping = {} # invMapping stores all the mappings from the SQL query
  usedMapping = {}
  while i < len(words):
    if i < len(words) - 2 and (words[i] + ' ' + words[i+1] + ' ' + words[i + 2]) in mapping: 
      phrase = words[i] + ' ' + words[i+1] + ' ' + words[i + 2]
      typ = ""
      if phrase in usedMapping:
        typ = usedMmapping[phrase]
      else:
        typ = mapping[phrase]
        typNum[typ] = typNum.setdefault(typ, -1) + 1
        typ = typ + '@' + str(typNum[typ])
        usedMapping[phrase] = typ
        usedInvMapping[typ] = "'" + phrase + "'"

      words[i] = typ
      words[i + 1] = ''
      words[i + 2] = ''
      i += 2
    elif i < len(words) - 1 and (words[i] + ' ' + words[i+1]) in mapping:
      typ = ""
      phrase = words[i] + ' ' + words[i+1]
      if phrase in usedMapping:
        typ = usedMmapping[phrase]
      else:
        typ = mapping[phrase]
        typNum[typ] = typNum.setdefault(typ, -1) + 1
        typ = typ + '@' + str(typNum[typ])
        usedMapping[phrase] = typ
        usedInvMapping[typ] = "'" + phrase + "'"

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
        usedInvMapping[typ] = "'" + phrase + "'"

      words[i] = typ

    elif words[i] == "usa" or words[i] == "us" or words[i] == "america":
      words[i] = "united states"

    i += 1

  # substitute usedMapping in SQL
  for i in range(0, len(tokens)):
    if tokens[i][1:-1] in usedMapping:
      tokens[i] = usedMapping[tokens[i][1:-1]]

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