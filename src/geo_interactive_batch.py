import gflags
FLAGS = gflags.FLAGS
import itertools
import sys
import random
import json

from geo_templatize import process, deanonymize

from generate import generateFromList
from Query import Query
from SqlMetric import SqlMetric, compute
import subprocess
import os
import math
import shutil
from Schema import Schema

class Interactive:
  def __init__(self, dropout, num_folds, seq_length, seed, epochs, embedding_file, skip_first, rnn_size, word_vec_size, nl_file,
      sql_file, plot_file, batch_size, grammar_file, data_dir, models_dir, db, schema, ppscale, ppfile, db_host, db_user, db_pass):
    self.num_folds = num_folds
    self.db = db
    self.ppscale = ppscale
    self.ppfile = ppfile
    self.schema = schema
    self.dropout = dropout

    self.data = []
    self.grammar_file = grammar_file
    self.BATCH_SIZE = batch_size
    self.data_dir = data_dir
    self.models_dir = self.data_dir + '/' + models_dir
    self.plot_file = self.data_dir + '/' + plot_file
    self.rnn_size = rnn_size
    self.word_vec_size = word_vec_size
    self.skip_first = skip_first
    self.embedding_file = embedding_file
    self.epochs = epochs
    self.seed = seed
    self.seq_length = seq_length
    self.db_host = db_host
    self.db_user = db_user
    self.db_pass = db_pass


    try:
      os.remove(self.plot_file)
    except OSError:
      pass

    random.seed(self.seed)

    self.data = self.getData(nl_file, sql_file)

  def getData(self, nl_file, sql_file):
    data = []
    for nl, sql in itertools.izip(open(nl_file, 'r'), open(sql_file, 'r')):
      (anon_nl, t_sql, map_nl) = process(nl.strip(), sql.strip())
      data.append((anon_nl, map_nl, nl, sql))
    return data


  def cleanup(self):
    try:
      shutil.rmtree(self.models_dir)
    except:
      pass
    os.makedirs(self.models_dir)

  def plot(self, fold, batch, isTest, correct, total):
    f = open(self.plot_file, 'a')
    elems = [fold, batch, int(isTest), correct, total]
    f.write('\t'.join([str(x) for x in elems]) + '\n')
    f.close()

  def makeFolder(self, fold, batch):
    prefix = self.data_dir + '/' + str(fold) + '_' + str(batch)
    if not os.path.exists(prefix):
      os.makedirs(prefix)
    return prefix

  def reloadTemplates(self):
    sys.stderr.write('Resetting templates\n')
    self.grammar = []
    for g in open(self.grammar_file, 'r'):
      self.grammar.append(g.strip())

  def run(self): # orchestrator
    score = 0

    for fold in range(0, self.num_folds):
      self.reloadTemplates()
      self.cleanup()
      if not self.skip_first:
        self.trainNeuralModel(self.models_dir) # train model from seed data
      self.createFold()

      first = True
      for batch in self.train:
        isTest = batch == (len(self.train) - 1)
        prefix = self.makeFolder(fold, batch)
        if not first or not self.skip_first:
          batch_score = self.testNeuralModel(prefix, batch)  # First test to see how many are wrong
          sys.stderr.write('Fold ' + str(fold) + ' Batch ' + str(batch) + ' score = ' + str(batch_score))
          self.plot(fold, batch, isTest, batch_score, len(self.train[batch]))
        first = False
        if not isTest: # last batch is the test set
          self.ingestFoldBatch(batch, prefix)
          self.trainNeuralModel(self.models_dir)

  def createFold(self):
    random.shuffle(self.data)
    self.train = {} # One key per batch

    for i in range(0, len(self.data)):
      self.train.setdefault(i / self.BATCH_SIZE, []).append(i)

  def ingestFoldBatch(self, batch, prefix):
    for i in self.train[batch]:
      (anon_nl, map_nl, nl, sql) = self.data[i]

      (t_nl, t_sql, m_nl) = process(nl.strip(), sql.strip())
      self.grammar.append(t_nl + '\t' + t_sql)
    f = open(prefix + '/grammar.txt', 'w')
    for g in self.grammar:
      f.write(g + '\n')
    f.close()
    sys.stderr.write('Ingested grammar. Grammar size is now  ' + str(len(self.grammar)) + '\n')

  def prepareword2vecFiles(self, corpus, prefix):
    words = []
    for (n, s) in corpus:
      ws = n.strip().split()
      for w in ws:
        if w not in words:
          words.append(w)

    f = open(prefix + '/word2vec.vecs', 'w')
    g = open(prefix + '/word2vec.dict', 'w')
    g.write('<blank> 1\n')
    g.write('<unk> 2\n')
    g.write('<s> 3\n')
    g.write('</s> 4\n')
    num = 5
    for line in open(self.embedding_file, 'r'):
      cols = line.strip().split()
      if cols[0] in words:
        f.write(line)
        g.write(cols[0] + ' ' + str(num) + '\n')
        num += 1
    self.word2vec_size = num - 1
    f.close()
    g.close()

  def generateFiles(self, corpus, prefix):
    tr_nl = open(prefix + '/train.nl', 'w')
    tr_sql = open(prefix + '/train.sql', 'w')
    te_nl = open(prefix + '/val.nl', 'w')
    te_sql = open(prefix +  '/val.sql', 'w')

    num = 0
    for (n, s) in corpus:
      if random.random() < 0.10 or num < 2:
        te_nl.write(n + '\n')
        te_sql.write(s + '\n')
      else:
        tr_nl.write(n + '\n')
        tr_sql.write(s + '\n')
      num += 1

    tr_nl.close()
    tr_sql.close()
    te_nl.close()
    te_sql.close()


  def buildNeuralData(self, prefix):
    # split data into train and valid and create files
    cmd = ('python', 'preprocess.py',
           '--srcfile', prefix + '/train.nl',
           '--targetfile', prefix + '/train.sql',
           '--srcvalfile', prefix + '/val.nl',
           '--targetvalfile', prefix + '/val.sql',
           '--word2vecfile', prefix + '/word2vec.dict',
           '--outputfile', prefix + '/s2',
           '--batchsize', '100',
           '--seqlength', str(self.seq_length),
           '--vocab_unk_threshold','1')
    print(cmd)
    output = subprocess.check_output(cmd)
    print(output)

  def trainCommand(self, prefix):
    cmd = ('th', 'train.lua',
           '-src_dict', prefix + '/s2.src.dict',
           '-seed', str(self.seed),
           '-targ_dict', prefix + '/s2.targ.dict',
           '-data_file', prefix + '/s2-train.hdf5',
           '-val_data_file', prefix + '/s2-val.hdf5',
           '-savefile', self.models_dir + '/s2s-model',
           '-max_batch_l', '100',
           '-num_layers', '1',
           '-dropout', str(self.dropout),
           '-gpuid', str(1),
           '-print_every', '200',
           '-epochs', str(self.epochs),
           '-rnn_size', str(self.rnn_size),
           '-word2vec_size', str(self.word2vec_size),
           '-word2vec_dim', '300',
           '-word2vecfile', prefix + '/word2vec.vecs',
           '-word_vec_size', str(self.word_vec_size),
           '-brnn', str(1),
           '-lr_decay', '0.8',
           '-predict', '0',
           '-optim', 'adam',
           '-learning_rate', '0.001'
           )
    print ' '.join(cmd)
    subprocess.check_output(cmd)
  
  def testNeuralModel(self, prefix, batch):
    sys.stderr.write('Testing model at: ' + prefix + '\n')

    t_nl_file = open(prefix + '/dev.nl', 'w')
    for i in self.train[batch]:
      (anon_nl, map_nl, nl, sql) = self.data[i]
      t_nl_file.write(anon_nl + '\n')
    t_nl_file.close()

    cmd = ('th', 'beam.lua',
           '-model', self.models_dir + '/s2s-model_final.t7',
           '-src_file', prefix + '/dev.nl',
           '-output_file', prefix + '/dev.sql.pred',
           '-gpuid', str(1),
           '-src_dict', self.models_dir + '/s2.src.dict',
           '-targ_dict', self.models_dir + '/s2.targ.dict',
           '-beam', '5',
           '-max_sent_l', str(self.seq_length + 50),
           '-score_gold', '0',
           '-word2vec_dict', self.models_dir + '/word2vec.dict')
    print ' '.join(cmd)
    subprocess.check_output(cmd)

    # load the predictions
    self.prediction = []
    for line in open(prefix + '/dev.sql.pred', 'r'):
      self.prediction.append(line.strip())

    score = 0
    predPtr = 0
    for i in self.train[batch]:
      (anon_nl, map_nl, nl, sql) = self.data[i]
      p_sql = deanonymize(json.dumps(map_nl), self.prediction[predPtr]) #deanonymize with map
      predPtr += 1
      (corr, ran, err, num, gold, q_ret) = compute(self.db, 1, gold=sql, q1=p_sql, host=self.db_host, user=self.db_user, passwd=self.db_pass)

      score += corr

    return score


  def trainNeuralModel(self, prefix):
    corpus = generateFromList(self.grammar, self.schema, self.db, self.ppscale, self.ppfile, '../data/ppdb/stopwords.txt', self.db_host, self.db_user, self.db_pass)
    self.prepareword2vecFiles(corpus, prefix)
    self.generateFiles(corpus, prefix)
    self.buildNeuralData(prefix)
    self.trainCommand(prefix)

if __name__ == '__main__':

  gflags.DEFINE_string("train_nl", "../data/geo/geo_train.nl", "Training File Nl")
  gflags.DEFINE_string("train_sql", "../data/geo/geo_train.sql", "Training File Sql")
  gflags.DEFINE_string("init_grammar_file", "../data/grammar.sql", "Initial grammar filel")
  gflags.DEFINE_string("embedding_file", "../data/word2vec/word2vec.txt", "Embedding file. word2vec or Word2vec or your own")
  gflags.DEFINE_string("schema", "../data/geo/geo.schema", "grammar file")
  gflags.DEFINE_string("data_dir", "../data/geo/tmp/", "Directory for temporary data")
  gflags.DEFINE_string("models_dir", "../data/geo/tmp/models", "Directory for temporary models")
  gflags.DEFINE_string("db", "geo", "database to run queries")
  gflags.DEFINE_integer("batch_size", 50, "batch size")
  gflags.DEFINE_string("plot_file", 'trace.txt', "File to store results")
  gflags.DEFINE_integer("rnn_size", 500, "rnn size")
  gflags.DEFINE_integer("word_vec_size", 500, "word vec size")
  gflags.DEFINE_integer("num_folds", 10, "which fold")
  gflags.DEFINE_boolean("skip_first", False, "Skip initial training and testing")
  gflags.DEFINE_integer("ppscale", 0, "Number of paraphrases to expand to")
  gflags.DEFINE_integer("seed", 1006, "NN seed")
  gflags.DEFINE_integer("seq_length", 100, "max sequence length")
  gflags.DEFINE_integer("epochs", 30, "Number of training epochs")
  gflags.DEFINE_float("dropout", 0.5, "Dropout")
  gflags.DEFINE_string("db_host", "", "")
  gflags.DEFINE_string("db_user", "", "")
  gflags.DEFINE_string("db_pass", "", "")
  
  FLAGS(sys.argv)

  s = Interactive(
    nl_file=FLAGS.train_nl,
    sql_file=FLAGS.train_sql,
    db=FLAGS.db,
    schema=FLAGS.schema,
    grammar_file=FLAGS.init_grammar_file,
    ppscale=FLAGS.ppscale,
    ppfile='../data/ppdb/ppdb-l-combined',
    data_dir=FLAGS.data_dir,
    models_dir=FLAGS.models_dir,
    batch_size=FLAGS.batch_size,
    plot_file=FLAGS.plot_file,
    rnn_size=FLAGS.rnn_size,
    word_vec_size=FLAGS.word_vec_size,
    skip_first=FLAGS.skip_first,
    embedding_file=FLAGS.embedding_file,
    epochs=FLAGS.epochs,
    seed=FLAGS.seed,
    seq_length=FLAGS.seq_length,
    num_folds=FLAGS.num_folds,
    dropout=FLAGS.dropout,
    db_host=FLAGS.db_host,
    db_user=FLAGS.db_user,
    db_pass=FLAGS.db_pass
  )
  #print(vars(s))
  s.run()

