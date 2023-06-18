from pathlib import Path
from typing import Annotated, Optional

import h5py
import numpy
import tqdm
import typer
from click.exceptions import UsageError

from .config import get_config, get_detector, psi_gain_maps
from .morgul_correct import correct_frame
from .util import BOLD, NC


def average_pedestal(gain_mode, filename):
    with h5py.File(filename) as f:
        d = f["data"]
        s = d.shape
        image = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)
        mask = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.uint32)

        for j in tqdm.tqdm(range(s[0]), desc=f"Gain Mode {gain_mode}"):
            i = d[j]
            gain = numpy.right_shift(i, 14)
            valid = gain == gain_mode
            i *= valid
            mask += valid
            image += i

        # cope with zero valid observations

        mask[mask == 0] = 1

        return image / mask


def mask(filename, pedestals, gain_maps, energy):
    """Use the data given in filename to derive a trusted pixel mask"""

    with h5py.File(filename) as f:
        s = f["data"].shape

        # fetch the correct gain maps for this module

        image = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)
        square = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)

        try:
            assert f["gainmode"][()].decode() == "dynamic"
        except KeyError:
            pass

        d = f["data"]

        # compute sum, sum of squares down stack
        for j in tqdm.tqdm(range(d.shape[0]), desc="Mask"):
            frame = correct_frame(d[j], pedestals, gain_maps, energy)
            image += frame
            square += numpy.square(frame)
        mean = image / d.shape[0]
        var = square / d.shape[0] - numpy.square(mean)
        mean[mean == 0] = 1
        disp = var / mean
        print(f"Masking {numpy.count_nonzero(disp > 3)} pixels")
        return (disp > 3).astype(numpy.uint32)


def pedestal(
    energy: Annotated[
        float, typer.Option("-e", "--energy", help="photon energy (keV)")
    ],
    p0: Annotated[
        Optional[Path],
        typer.Option("-0", help="Data file for pedestal run at gain mode 0"),
    ],
    p1: Annotated[
        Optional[Path],
        typer.Option("-1", help="Data file for pedestal run at gain mode 1"),
    ],
    p2: Annotated[
        Optional[Path],
        typer.Option("-2", help="Data file for pedestal run at gain mode 2"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Argument(
            help="Name for the output HDF5 file. Default: <detector>_pedestal.h5",
        ),
    ],
):
    """
    Calibration setup for Jungfrau
    """
    detector = get_detector()
    print(f"Using detector: {BOLD}{detector}{NC}")

    output = output or Path(f"{detector}_pedestal.h5")
    with h5py.File(output, "w") as f:
        pedestals = {}
        if p0:
            p0 = average_pedestal(0, p0)
            pedestals["p0"] = p0
            f.create_dataset("p0", data=p0)
        if p1:
            p1 = average_pedestal(1, p1)
            pedestals["p1"] = p1
            f.create_dataset("p1", data=p1)
        if p2:
            p2 = average_pedestal(3, p2)
            pedestals["p2"] = p2
            f.create_dataset("p2", data=p2)
        if flat:
            assert "p0" in pedestals
            gain_maps = psi_gain_maps(detector)

            with h5py.File(flat, "r") as _f:
                r = int(_f["row"][()])
                c = int(_f["column"][()])

            config = get_config()
            module = config[f"{detector}-{c}{r}"]["module"]
            maps = gain_maps[module]
            m = mask(flat, pedestals, maps, energy)
            f.create_dataset("mask", data=m)
