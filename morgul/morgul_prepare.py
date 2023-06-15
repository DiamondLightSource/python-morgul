from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h5py
import numpy
import tqdm

from .config import get_known_detectors, psi_gain_maps

BOLD = "\033[1m"
R = "\033[31m"
NC = "\033[0m"


def init(detector: str) -> None:
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

    # THIS IS WRONG at the moment as it needs to work on corrected data
    # at this point the data *are not* corrected so this needs to also
    # encode the correction procedure

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
        return (disp > 3).astype(numpy.uint32)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibration setup for Jungfrau",
    )
    parser.add_argument(
        "detector",
        choices=get_known_detectors(),
        help="Which detector to run calibration preparations for.",
    )
    parser.add_argument(
        "-i",
        "--init",
        action="store_true",
        help="Create initial files. If specified, must specify other file-based flags.",
    )
    parser.add_argument(
        "-0",
        "--pedestal-0",
        dest="p0",
        help="Data file for pedestal run at gain mode 0",
        type=Path,
    )
    parser.add_argument(
        "-1",
        "--pedestal-1",
        dest="p1",
        help="Data file for pedestal run at gain mode 1",
        type=Path,
    )
    parser.add_argument(
        "-2",
        "--pedestal-2",
        dest="p2",
        help="Data file for pedestal run at gain mode 2",
        type=Path,
    )
    parser.add_argument(
        "-f",
        "--flat",
        dest="f",
        help="Data file of flat field data, to use for mask calculation",
        type=Path,
    )
    parser.add_argument(
        "-o",
        dest="output",
        help="Name for the output HDF5 file. Default: <detector>_pedestal.h5",
        metavar="OUTPUT.h5",
        type=Path,
    )
    args = parser.parse_args()

    # Ensure we must request one or the other
    has_source_files = args.p0 or args.p1 or args.p2 or args.f
    if args.init and has_source_files:
        sys.exit(
            f"{R}Error: Cannot specify pedestal/flatfield run and initial file runs at the same time.{NC}"
        )
    elif not args.init and not has_source_files:
        # The user neither provided source files nor requested init
        parser.print_help()
        sys.exit(1)

    if args.init:
        init(args.detector)
        return

    args.output = args.output or Path(f"{args.detector}_pedestal.h5")
    with h5py.File(args.output, "w") as f:
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
