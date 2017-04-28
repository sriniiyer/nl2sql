import gflags
FLAGS = gflags.FLAGS
import sys
import json
import itertools
from Query import Query, tokenizeNL
from Schema import Schema
import re

class Anonymizer:
  def anonymize(self, s, schema):
    s = tokenizeNL(s)
    anonStructure = schema.getAnonymizationStructure(s)
    return (s, anonStructure)

  def anonymizeFile(self, nlfile, anonfile, mapfile, schema, db, stopfile):
    schemaObj = Schema(schema, stopfile)
    schemaObj.buildIndex('/tmp/' + db + '.index', db)
    anonfile = open(anonfile, 'w')
    mapfile = open(mapfile, 'w')

    for line in open(nlfile, 'r'):
      (anon, mp) = self.anonymize(line, schemaObj)
      anonfile.write(anon + '\n')
      mapfile.write(json.dumps(mp) + '\n')

    anonfile.close()
    mapfile.close()
  
  def deanonymize(self, s, m, schemaObj):
    query = Query('placeholder', s)
    # Take care of joins in the SQL
    try:
      query.fillInJoins(schemaObj)
    except IndexError:
      pass
    except KeyError:
      pass
    
    query.deanonymize(m)
    return query


  def deanonymizeFile(self, mapfile, sqlfile, schema, stopfile):
    schemaObj = Schema(schema, stopfile)
    mapfile = open(mapfile, 'r').readlines()
    outfile = open(sqlfile + '.deanon', 'w')
    sqlfile = open(sqlfile, 'r').readlines()
    for m, s in itertools.izip(mapfile, sqlfile):
      q = self.deanonymize(s, json.loads(m), schemaObj)
      deanon = q.getQuery()
      outfile.write(deanon + '\n')
    outfile.close()

def main(): 
  gflags.DEFINE_bool("reverse", False, "De anonymize?")
  gflags.DEFINE_string("nlfile", "val_nl.txt", "file to be anonymised")
  gflags.DEFINE_string("sqlfile", "val_sql.txt", "sql file to be deanonymised")
  gflags.DEFINE_string("anonfile", "val_nl_anon.txt", "anonymized file")
  gflags.DEFINE_string("stop_file", "../data/ppdb/stopwords.txt", "stopwords file")
  gflags.DEFINE_string("mapfile", "val_nl_map.txt", "mapping file")
  gflags.DEFINE_string("db", "geo", "")
  gflags.DEFINE_string("schema", "geo.schema", "grammar file")
  FLAGS(sys.argv)

  anony = Anonymizer()

  if FLAGS.reverse: # De anonymization
    anony.deanonymizeFile(FLAGS.mapfile, FLAGS.sqlfile, FLAGS.schema, FLAGS.stop_file)  
  else: # anonymization
    anony.anonymizeFile(FLAGS.nlfile, FLAGS.anonfile, FLAGS.mapfile, FLAGS.schema, FLAGS.db, FLAGS.stop_file)

if __name__ == '__main__':
  main()