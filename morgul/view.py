import enum
import logging
from pathlib import Path
from typing import Annotated

import h5py
import napari
import typer

from . import config
from .util import NC, B, G, R

logger = logging.getLogger(__name__)


class FileKind(enum.Enum):
    # UNKNOWN = enum.auto()
    GAIN_MAP = enum.auto()
    MASK = enum.auto()
    PEDESTAL = enum.auto()
    RAW = enum.auto()
    CORRECTED = enum.auto()


def determine_kinds(root: h5py.Group) -> set[FileKind]:
    """Given an HSD5 data group, work out what kind of data it contains"""
    detector = config.get_detector()
    modules = config.get_known_modules_for_detector(detector)
    kinds = set()
    # Work out what sort of file we have
    module_subgroups = [
        x for x in modules if x in root and isinstance(root[x], h5py.Group)
    ]
    for module in module_subgroups:
        if "g0" in root[module] or "g1" in root[module] or "g2" in root[module]:
            kinds.add(FileKind.GAIN_MAP)
        if "mask" in root[module]:
            kinds.add(FileKind.MASK)
        if any(
            x.startswith("pedestal_")
            for x in root[module]
            if isinstance(root[module][x], h5py.Dataset)
        ):
            kinds.add(FileKind.PEDESTAL)
    if "data" in root and isinstance(root["data"], h5py.Dataset):
        if root["data"].attrs.get("corrected", False):
            kinds.add(FileKind.CORRECTED)
        else:
            kinds.add(FileKind.RAW)

    return kinds


def determine_kind(root: h5py.Group) -> FileKind | None:
    """Return a single file kind"""
    kinds = determine_kinds(root)
    if kinds:
        return sorted(kinds, key=lambda x: x.value)[-1]
    return None


def view(filename: Annotated[Path, typer.Argument(help="Data file to view")]):
    """Launch a napari-based viewer"""

    with h5py.File(filename, "r") as f:
        viewer = napari.Viewer()
        kind = determine_kind(f)
        if kind is None:
            logger.error(f"{R}Error: Could not determine file kind for {filename}{NC}")
            raise typer.Abort()

        logger.info(f"Opening {B}{filename}{NC} as {G}{kind.name.title()}{NC}")
        if kind == FileKind.PEDESTAL:
            for module in "M420", "M418":
                for mode in 0, 1, 2:
                    viewer.add_image(
                        f[module][f"pedestal_{mode}"][()], name=f"{module}/{mode}"
                    )
        elif kind == FileKind.RAW:
            viewer.add_image(f["data"], name=f"{filename}")
        else:
            logger.error(
                f"{R}Error: File kind {kind.name} is not currently supported{NC}"
            )
            raise typer.Abort()

        napari.run()
