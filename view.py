import sys

import numpy
from matplotlib import pyplot

m = numpy.fromfile(open(sys.argv[1], "r"), dtype=numpy.float64, count=-1).reshape(
    512, 1024
)

print(numpy.mean(m))

pyplot.imshow(m, vmin=0, vmax=1)
pyplot.show()
