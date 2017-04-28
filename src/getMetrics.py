import sys
from SqlMetric import SqlMetric
import gflags
FLAGS = gflags.FLAGS

def prettyPrint(score):
  (correct, total, percent) = score
  print "Correct=" + str(correct) + " , Total=" + str(total) + " , Percent=" + str(percent)

if __name__ == '__main__':
  gflags.DEFINE_string('reffile', '', 'File with true references')
  gflags.DEFINE_string('methodfile', '', 'File with predictions')
  gflags.DEFINE_bool('debug', False, 'Display debugging information')
  gflags.DEFINE_string('debugfile', '', 'file to store debug stats')
  gflags.DEFINE_string('db', 'geo', 'database for denotations')
  gflags.DEFINE_string("host", "", "")
  gflags.DEFINE_string("user", "", "")
  gflags.DEFINE_string("passwd", "", "")
  sys.argv = FLAGS(sys.argv)

  m = SqlMetric(FLAGS.db, FLAGS.debug, FLAGS.debugfile, 'ignore')
  score = m.computeFromFiles(FLAGS.reffile, FLAGS.methodfile, FLAGS.host, FLAGS.user, FLAGS.passwd)
  prettyPrint(score)
