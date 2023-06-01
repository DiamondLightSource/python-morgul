import sys

import numpy
import h5py


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

    # set non-null value where it would be null
    stddev[stddev == 0] = 1.0

    print(f"Mean variance: {numpy.mean(stddev):.2f} 12keV photons")

    delta0 = (mean - imin) / stddev

    print(f"Most negative: {numpy.max(delta0):.2f} sigmas")

    print(f"Most negative: {numpy.max(mean - imin):.2f} 12keV photons")


if __name__ == "__main__":
    main(*sys.argv[1:])
