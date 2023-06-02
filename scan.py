import sys

import numpy
import h5py

from matplotlib import pyplot

def main(datafile, gainfile, outputfile):
    data = h5py.File(datafile, "r")
    gain = numpy.fromfile(open(gainfile, "r"), dtype=numpy.float64, count=-1).reshape(
        6, 512, 1024
    )
    output = h5py.File(outputfile, "w")

    raw = data["data"]

    n = raw.shape[0]

    image = numpy.zeros(shape=(raw.shape[1:]), dtype=numpy.float64)
    image2 = numpy.zeros(shape=(raw.shape[1:]), dtype=numpy.float64)

    imin = None
    imax = None

    igain = 1.0 / gain[0]

    for j in range(n):
        tmp = raw[j, :, :]
        tmp[tmp > 0x3FFF] = 0
        tmp = tmp * igain
        if imin is None:
            imin = tmp
            imax = tmp
        else:
            imin = numpy.minimum(imin, tmp)
            imax = numpy.maximum(imax, tmp)
        image += tmp
        image2 += tmp * tmp

    mean = image / n
    stddev = numpy.sqrt(image2 / n - mean * mean)

    h, e = numpy.histogram(stddev, bins=100, range=(0, 5))

    # identify pixels which are (i) too noisy and (ii) not noisy enough
    # using Tukey outlier definitions
    q1, q3 = numpy.percentile(stddev, [25, 75])
    iqr = q3 - q1
    print(f"Too quiet: {numpy.count_nonzero(stddev < (q1 - 3 * iqr))}")
    print(f"Too noisy: {numpy.count_nonzero(stddev > (q3 + 3 * iqr))}")

    mask = numpy.ones(shape=(raw.shape[1:]), dtype=numpy.int32)

    mask[stddev < (q1 - 3 * iqr)] = 0
    mask[stddev > (q3 + 3 * iqr)] = 0

    imin *= mask
    imax *= mask

    h, e = numpy.histogram(imax - imin, bins=100, range=(0, 100), weights=mask)

    for j in range(len(h)):
        print(f"{e[j]:.2f} {e[j+1]:.2f}, {h[j]}")

    pyplot.imshow(stddev * mask, vmin=0, vmax=1)
    pyplot.colorbar()
    pyplot.show()

if __name__ == "__main__":
    main(*sys.argv[1:])
