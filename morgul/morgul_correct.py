from __future__ import annotations

import argparse
import logging
import os

import h5py
import hdf5plugin
import numpy
import tqdm

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


def correct() -> None:
    pass


def main():
    parser = argparse.ArgumentParser(
        description="Correction program for Jungfrau",
    )
    parser.add_argument("detector")
    parser.add_argument(
        "-m", "--module", dest="module", help="module data taken from i.e. 0, 1, ..."
    )
    parser.add_argument(
        "-p", "--pedestal", dest="pedestal", help="pedestal data from this module"
    )
    parser.add_argument(
        "-d", "--data", dest="data", help="data to correct from this module"
    )
    parser.add_argument("-e", "--energy", dest="energy", help="photon energy (keV)")
    args = parser.parse_args()

    assert args.detector
    assert args.energy

    energy = float(args.energy)

    pedestals = get_pedestals(args.pedestal)
    maps = psi_gain_maps(args.detector)

    g012 = maps[args.module]

    output = args.data.replace(".h5", "_corrected.h5")

    assert not os.path.exists(output)

    # FIXME need to add the embiggen code

    with h5py.File(args.data, "r") as i, h5py.File(output, "w") as f:
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
            gain = numpy.right_shift(raw, 14)
            m0 = pedestals["p0"] != 0
            frame = (
                (gain == 0) * (numpy.bitwise_and(raw, 0x3FFF)) * m0 - pedestals["p0"]
            ) / (g012[0] * energy)
            if "p1" in pedestals:
                m1 = pedestals["p1"] != 0
                frame += (
                    (gain == 1)
                    * ((numpy.bitwise_and(raw, 0x3FFF)) * m1 - pedestals["p1"])
                ) / (g012[1] * energy)
            if "p2" in pedestals:
                m2 = pedestals["p2"] != 0
                frame += (
                    (gain == 3)
                    * ((numpy.bitwise_and(raw, 0x3FFF)) * m2 - pedestals["p2"])
                ) / (g012[2] * energy)
            d[j] = embiggen(numpy.around(frame))


if __name__ == "__main__":
    main()
