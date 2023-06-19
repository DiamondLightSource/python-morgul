from pathlib import Path
from typing import Annotated

import h5py
import napari
import typer


def view(filename: Annotated[Path, typer.Argument(help="Data file to view")]):
    """Launch a napari-based viewer"""
    with h5py.File(filename, "r") as f:
        viewer = napari.Viewer()
        for module in "M420", "M418":
            for mode in 0, 1, 2:
                viewer.add_image(
                    f[module][f"pedestal_{mode}"][()], name=f"{module}/{mode}"
                )
        napari.run()
