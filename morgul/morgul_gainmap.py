from typing import Annotated

import h5py
import typer

from .config import psi_gain_maps


def gainmap(
    detector: Annotated[
        str, typer.Argument(help="Which detector to write gain correction maps")
    ]
) -> None:
    """
    Convert binary gain-map files to HDF5 datasets
    """
    maps = psi_gain_maps(detector)

    with h5py.File(f"{detector}_calib.h5", "w") as f:
        for k in sorted(maps):
            g = f.create_group(k)
            g012 = maps[k]
            for j in 0, 1, 2:
                g.create_dataset(f"g{j}", data=g012[j])
