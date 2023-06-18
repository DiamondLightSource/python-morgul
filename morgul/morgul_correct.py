import logging
from pathlib import Path
from typing import Annotated

import h5py
import hdf5plugin
import numpy
import tqdm
import typer

from .config import psi_gain_maps

logger = logging.getLogger(__name__)


def get_pedestals(pedestal_file):
    pedestals = {}

    with h5py.File(pedestal_file, "r") as f:
        for k in "p0", "p1", "p2":
            if k in f:
                pedestals[k] = f[k][()]

    return pedestals


def embiggen(packed):
    """Unpack the data from ASICS to the pixel-doubled form, masking the affected
    pixels so this has the result of just slightly embiggening the images. Since
    this is a copy have it also do the inversion (pay attention people.)"""

    assert packed.shape == (512, 1024)

    bigger = numpy.full((514, 1030), 0xFFFFFFFF, dtype=numpy.int32)

    for i in range(2):
        for j in range(4):
            for k in range(1, 255):
                I = i * 256
                _I = 513 - i * 258 - k
                J = j * 256
                _J = j * 258 - 1 if j else 0
                bigger[_I, (_J + 1) : (_J + 255)] = packed[I + k, (J + 1) : (J + 255)]

    return bigger


def correct_frame(raw, pedestals, g012, energy):
    """Correct pixel values to photons in frame"""

    gain = numpy.right_shift(raw, 14)
    m0 = pedestals["p0"] != 0
    frame = ((gain == 0) * (numpy.bitwise_and(raw, 0x3FFF)) * m0 - pedestals["p0"]) / (
        g012[0] * energy
    )
    if "p1" in pedestals:
        m1 = pedestals["p1"] != 0
        frame += (
            (gain == 1) * ((numpy.bitwise_and(raw, 0x3FFF)) * m1 - pedestals["p1"])
        ) / (g012[1] * energy)
    if "p2" in pedestals:
        m2 = pedestals["p2"] != 0
        frame += (
            (gain == 3) * ((numpy.bitwise_and(raw, 0x3FFF)) * m2 - pedestals["p2"])
        ) / (g012[2] * energy)
    return frame


def correct(
    detector: Annotated[
        str, typer.Argument(help="Which detector to run calibration preparations for")
    ],
    module: Annotated[
        str,
        typer.Option("-m", "--module", help="module data taken from i.e. 0, 1, ..."),
    ],
    pedestal: Annotated[
        Path, typer.Option("-p", "--pedestal", help="pedestal data from this module")
    ],
    data: Annotated[
        Path, typer.Option("-d", "--data", help="data to correct from this module")
    ],
    energy: Annotated[
        float, typer.Option("-e", "--energy", help="photon energy (keV)")
    ],
):
    """Correction program for Jungfrau"""

    pedestals = get_pedestals(pedestal)
    maps = psi_gain_maps(detector)

    g012 = maps[module]

    output = data.parent / f"{data.stem}_corrected{data.suffix}"

    assert not output.exists()

    # FIXME need to add the embiggen code

    with h5py.File(data, "r") as i, h5py.File(output, "w") as f:
        r = i["data"]
        s = r.shape
        d = f.create_dataset(
            "data",
            shape=(s[0], 514, 1030),
            dtype=numpy.int32,
            chunks=(1, 514, 1030),
            **hdf5plugin.Bitshuffle(lz4=True),
        )
        for j in tqdm.tqdm(range(s[0])):
            raw = r[j]
            frame = correct_frame(raw, pedestals, g012, energy)
            d[j] = embiggen(numpy.around(frame))