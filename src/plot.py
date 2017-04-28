
import gflags
FLAGS = gflags.FLAGS
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

test_correct = 0
test_total = 0
batch_sum = {}
batch_total = {}
max_batch = 0
wrongs = 0
totals = 0

gflags.DEFINE_string("trace_file", "something", "file containing trace")
FLAGS(sys.argv)

for line in open(FLAGS.trace_file, 'r'):
  (fold, batch, isTest, correct, total) = line.strip().split('\t')
  batch = float(batch)
  if batch > max_batch:
    max_batch = batch
  batch_sum[batch] = batch_sum.setdefault(batch, 0) + int(correct)
  batch_total[batch] = batch_total.setdefault(batch, 0) + int(total)
  if int(isTest) == 0:
    wrongs +=  int(total) - int(correct)
    totals += int(total)


x = np.arange(0, max_batch + 1, 1)
plt.ylabel('Accuracy on next batch')
plt.title('Learning Trace for ' + FLAGS.trace_file)
plt.plot(x, [batch_sum[i] * 1.0 / batch_total[i] for i in x])
print(x)
print([batch_sum[i] * 1.0 / batch_total[i] for i in x])
print(str(wrongs * 100.0 / totals))
plt.grid(True)
plt.text(max_batch - 2, 0.3, 'Wrong: ' + str(wrongs * 100.0 / totals))
plt.ylim(0, 1.0)
plt.savefig('/tmp/trace.png')
plt.close()