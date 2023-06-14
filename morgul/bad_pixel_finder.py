import sys

import numpy
from matplotlib import pyplot

import h5py
import hdf5plugin

import tqdm

image = numpy.zeros(shape=(514, 1030), dtype=numpy.float64)
square = numpy.zeros(shape=(514, 1030), dtype=numpy.float64)

with h5py.File(sys.argv[1], "r") as f:
    d = f["data"]
    for j in tqdm.tqdm(range(d.shape[0])):
        image += d[j].astype(numpy.float64)
        square += numpy.square(d[j].astype(numpy.float64))
    mean = image / d.shape[0]
    var = square / d.shape[0] - numpy.square(mean)

    mean[mean == 0] = 1

    disp = var / mean

    pyplot.imshow(disp, vmin=0, vmax=5)
    pyplot.colorbar()
    pyplot.show()