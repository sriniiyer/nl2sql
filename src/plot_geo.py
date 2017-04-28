import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams.update({'font.size': 12})

x = np.arange(1, 13, 1)
plt.ylabel('Fraction Correct')
plt.xlabel('Stages')
plt.title('Simulated Interactive Learning on Geo880')
plt.plot(x,[0.136, 0.38, 0.55, 0.628, 0.64, 0.68, 0.748, 0.74, 0.736, 0.774, 0.806, 0.812], label="Ours")
plt.plot(x, [0.022, 0.354, 0.5, 0.62, 0.672, 0.676, 0.722, 0.762, 0.778, 0.758, 0.776, 0.798], '--', label="Without templates")
plt.plot(x, [0.112, 0.338, 0.452, 0.544, 0.602, 0.648, 0.644, 0.664, 0.728, 0.73, 0.762, 0.74], ':', label="Without paraphrasing")
plt.grid(True)
plt.legend(loc="lower right")
plt.ylim(0, 0.9)
plt.savefig('geo_interactive.eps', format='eps', dpi=100)
plt.close()