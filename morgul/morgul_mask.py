from pathlib import Path
from typing import Annotated, Optional

import h5py
import numpy
import tqdm
import typer

from .config import get_config, get_detector, psi_gain_maps
from .morgul_correct import correct_frame


def _calculate(filename, pedestals, gain_maps, energy):
    """Use the data given in filename to derive a trusted pixel mask"""

    with h5py.File(filename) as f:
        s = f["data"].shape

        # fetch the correct gain maps for this module
        image = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)
        square = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)

        gain_mode = f["gainmode"][()].decode()
        assert (
            gain_mode == "dynamic"
        ), f"Data with gain mode 'dynamic' (this is {gain_mode}) required for mask calculation"

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


def mask(
    pedestal: Annotated[
        Path,
        typer.Argument(
            help="Pedestal data file for the module(s), from 'morgul pedestal'. Used when correcting in order to calculate the mask."
        ),
    ],
    flat: Annotated[
        list[Path],
        typer.Argument(
            help="Flat-field data to use for mask generation. Multiple modules for a single time point can be passed, but must be present in the pedestal file."
        ),
    ],
    energy: Annotated[
        float, typer.Option("-e", "--energy", help="photon energy (keV)")
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "-o",
            help="Name for the output HDF5 file. Default: <detector>_<module>_<exptime>ms_mask.h5",
        ),
    ] = None,
):
    """Prepare a pixel mask from flatfield data"""
    print(f"Running generation for: {flat}")
    # assert "p0" in pedestals
    detector = get_detector()
    gain_maps = psi_gain_maps(detector)

    with h5py.File(flat, "r") as _f:
        r = int(_f["row"][()])
        c = int(_f["column"][()])

    config = get_config()
    module = config[f"{detector}-{c}{r}"]["module"]
    maps = gain_maps[module]
    m = _calculate(flat, maps)

    output = Path(f"{detector}_{module}_mask.h5")
    with h5py.File(output, "w") as f:
        f.create_dataset("mask", data=m)
