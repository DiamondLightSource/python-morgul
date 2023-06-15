from __future__ import annotations

import argparse
import configparser
import glob
import os

import h5py
import numpy
import tqdm

hostname = os.uname()[1]
if "diamond.ac.uk" in hostname:
    hostname = "xxx.diamond.ac.uk"
install = os.path.dirname(os.path.realpath(__file__))


def get_config():
    """Get the local configuration from the installation directory"""
    configuration = configparser.ConfigParser()
    assert "morgul.ini" in configuration.read(os.path.join(install, "morgul.ini"))[0]
    return configuration


config = get_config()


def psi_gain_maps(detector):
    """Read gain maps from installed location, return as 3 x numpy array g0, g1, g2"""
    calib = config[hostname]["calibration"]
    result = {}
    for k in config.keys():
        if k.startswith(detector):
            module = config[k]["module"]
            gain_file = glob.glob(os.path.join(calib, f"M{module}_fullspeed", "*.bin"))
            assert len(gain_file) == 1
            shape = 3, 512, 1024
            count = shape[0] * shape[1] * shape[2]
            gains = numpy.fromfile(
                open(gain_file[0], "r"), dtype=numpy.float64, count=count
            ).reshape(*shape)
            result[f"M{module}"] = gains
    return result


def init(detector):
    maps = psi_gain_maps(detector)

    with h5py.File(f"{detector}_calib.h5", "w") as f:
        for k in sorted(maps):
            g = f.create_group(k)
            g012 = maps[k]
            for j in 0, 1, 2:
                g.create_dataset(f"g{j}", data=g012[j])


def average_pedestal(gain_mode, filename):
    with h5py.File(filename) as f:
        d = f["data"]
        s = d.shape
        image = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)
        mask = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.uint32)

        for j in tqdm.tqdm(range(s[0])):
            i = d[j]
            gain = numpy.right_shift(i, 14)
            valid = gain == gain_mode
            i *= valid
            mask += valid
            image += i

        # cope with zero valid observations

        mask[mask == 0] = 1

        return image / mask


def mask(filename):
    """Use the data given in filename to derive a trusted pixel mask"""

    with h5py.File(filename) as f:
        s = f["data"].shape

        image = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)
        square = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)

        try:
            assert f["gainmode"][()] == "dynamic"
        except KeyError:
            pass

        d = f["data"]

        # compute sum, sum of squares down stack
        for j in tqdm.tqdm(range(d.shape[0])):
            image += d[j].astype(numpy.float64)
            square += numpy.square(d[j].astype(numpy.float64))
        mean = image / d.shape[0]
        var = square / d.shape[0] - numpy.square(mean)
        mean[mean == 0] = 1
        disp = var / mean
        return (disp < 3).astype(numpy.uint32)


def main():
    parser = argparse.ArgumentParser(
        description="Calibration setup for Jungfrau",
    )
    parser.add_argument("detector")
    parser.add_argument(
        "-i", "--init", action="store_true", help="create initial files"
    )
    parser.add_argument(
        "-0", "--pedestal-0", dest="p0", help="pedestal run at gain mode 0"
    )
    parser.add_argument(
        "-1", "--pedestal-1", dest="p1", help="pedestal run at gain mode 1"
    )
    parser.add_argument(
        "-2", "--pedestal-2", dest="p2", help="pedestal run at gain mode 2"
    )
    parser.add_argument(
        "-f", "--flat", dest="f", help="flat field data to use for mask"
    )
    args = parser.parse_args()

    assert args.detector

    if args.init:
        init(args.detector)
        return

    with h5py.File(f"{args.detector}_pedestal.h5", "w") as f:
        if args.p0:
            p0 = average_pedestal(0, args.p0)
            f.create_dataset("p0", data=p0)
        if args.p1:
            p1 = average_pedestal(1, args.p1)
            f.create_dataset("p1", data=p1)
        if args.p2:
            p2 = average_pedestal(3, args.p2)
            f.create_dataset("p2", data=p2)
        if args.f:
            m = mask(args.f)
            f.create_dataset("mask", data=m)


if __name__ == "__main__":
    main()
