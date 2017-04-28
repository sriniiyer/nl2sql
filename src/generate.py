import re
from Query import Query
from Schema import Schema
import gflags
FLAGS = gflags.FLAGS
import sys
from ppdb import PPDB
import random

# recursive generation of examples
# by substituting one at a time
def generate(query, typeMap, schema, db, paraphraser, data):
  # First tokenize the English 
  sub = False
  for w in query.words:
    if '{' in w: # is a template token
      queries = query.apply(w, typeMap, schema)
      for q in queries:
        generate(q, typeMap, schema, db, paraphraser, data)
      sub = True
      break
  if not sub:
    query.output(schema, db, paraphraser, data)

def generateFromList(grammar, schema, db, ppscale, paraphrase_file, stopfile, host, user, passwd):
  typeMap = {}
  paraphraser = PPDB(paraphrase_file, ppscale)
  schema = Schema(FLAGS.schema, stopfile)
  data = []
  for line in grammar:
    if len(line) == 0 or line[0] == '#': # ignore empty lines and comments
      continue 
    elif "=>" in line: # A new type
      (lhs, rhs) = line.split('=>')
      typeMap[lhs.strip()] = [x.strip() for x in rhs.strip().split('|')]
    else: # A template
      templates = line.split('\t')
      sql = templates.pop()
      for t in templates:
        query = Query(t, sql, host=host, user=user, passwd=passwd)
        generate(query, typeMap, schema, db, paraphraser, data)
  return data


def generateFromFile(grammar, schema, db, ppscale, paraphrase_file, stop_file, prefix, noval, host, user, passwd):
  lines = []
  for line in open(grammar, 'r'):
    line = line.strip()
    lines.append(line)
  corpus = generateFromList(lines, schema, db, ppscale, paraphrase_file, stop_file, host, user, passwd)
  fnl = open(prefix + 'train.nl', 'w')
  fsql = open(prefix + 'train.sql', 'w')
  if not noval:
    vnl = open(prefix + 'val.nl', 'w')
    vsql = open(prefix + 'val.sql', 'w')

  random.shuffle(corpus)

  for (n, s) in corpus:
    if not noval and random.random() < 0.10:
      vnl.write(n + '\n')
      vsql.write(s + '\n')
    else:
      fnl.write(n + '\n')
      fsql.write(s + '\n')

  fnl.close()
  fsql.close()
  if not noval:
    vnl.close()
    vsql.close()


def main(): 
  gflags.DEFINE_string("grammar", "grammar.sql", "grammar file")
  gflags.DEFINE_string("prefix", "", "nlfile")
  gflags.DEFINE_string("paraphrase_file", "data/ppdb/ppdb-l-combined", "paraphrase file")
  gflags.DEFINE_string("stop_file", "data/ppdb/stopwords.txt", "stopwordsfile")
  gflags.DEFINE_string("schema", "s2.json", "grammar file")
  gflags.DEFINE_string("db", "s2_small", "database to run queries")
  gflags.DEFINE_string("host", "", "")
  gflags.DEFINE_string("user", "", "")
  gflags.DEFINE_string("passwd", "", "")
  gflags.DEFINE_integer("ppscale", 10, "Paraphrase scale")
  gflags.DEFINE_integer("noval", 0, "Paraphrase scale")
  FLAGS(sys.argv)

  generateFromFile(FLAGS.grammar, FLAGS.schema, FLAGS.db, FLAGS.ppscale, FLAGS.paraphrase_file, FLAGS.stop_file, FLAGS.prefix, FLAGS.noval, FLAGS.host, FLAGS.user, FLAGS.passwd)

if __name__ == '__main__':
  main()


