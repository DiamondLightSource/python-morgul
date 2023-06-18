from pathlib import Path
from typing import Annotated, Optional

import h5py
import typer

from .config import get_detector, psi_gain_maps
from .util import NC, B


def gainmap(
    ctx: typer.Context,
    output: Annotated[
        Optional[Path],
        typer.Argument(help="Output filename. Defaults to <detector>_calib.h5"),
    ] = None,
) -> None:
    """
    Convert binary gain-map files to HDF5 datasets
    """
    detector = get_detector()
    print(f"Using detector:         {B}{detector}{NC}")

    maps = psi_gain_maps(detector)

    output = output or Path(f"{detector}_calib.h5")
    print(f"Writing to output file: {B}{output}{NC} ...", end="", flush=True)
    with h5py.File(output, "w") as f:
        for k in sorted(maps):
            g = f.create_group(k)
            g012 = maps[k]
            for j in 0, 1, 2:
                g.create_dataset(f"g{j}", data=g012[j])
    print("done.")
