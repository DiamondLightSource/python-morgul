import sys

import numpy
from matplotlib import pyplot

m = numpy.fromfile(open(sys.argv[1], "r"), dtype=numpy.int32, count=-1).reshape(
    512, 1024
)

pyplot.imshow(m, vmin=0, vmax=4)
pyplot.colorbar()
pyplot.show()
