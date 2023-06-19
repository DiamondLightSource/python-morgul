import enum
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeAlias

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


ViewCallable: TypeAlias = Callable[[Path, h5py.Group], None]
view_functions: dict[FileKind, ViewCallable] = {}


def viewer(kind: FileKind) -> Callable[[ViewCallable], ViewCallable]:
    def _wrapped(view_func: ViewCallable) -> ViewCallable:
        if kind in view_functions:
            raise ValueError(f"Viewer for {kind} is already registered")
        view_functions[kind] = view_func
        return view_func

    return _wrapped


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


@viewer(FileKind.PEDESTAL)
def view_pedestal(filename: Path, root: h5py.Group) -> None:
    viewer = napari.Viewer()
    detector = config.get_detector()
    modules = config.get_known_modules_for_detector(detector)

    for module in modules:
        for mode in 0, 1, 2:
            name = f"pedestal_{mode}"
            if name in root[module]:
                viewer.add_image(root[module][name][()], name=f"{module}/{mode}")


@viewer(FileKind.RAW)
def view_raw(filename: Path, root: h5py.Group) -> None:
    viewer = napari.Viewer()

    viewer.add_image(root["data"], name=str(filename))


def view(filename: Annotated[Path, typer.Argument(help="Data file to view")]):
    """Launch a napari-based viewer"""

    with h5py.File(filename) as f:
        kind = determine_kind(f)
        logger.info(f"Opening {B}{filename}{NC} as {G}{kind.name.title()}{NC}")

        if kind is None:
            logger.error(
                f"{R}Error: Could not determine common file kind for {filename}{NC}"
            )
            raise typer.Abort()

        if kind in view_functions:
            view_functions[kind](filename, f)
            napari.run()
        else:
            logger.error(
                f"{R}Error: File kind {kind.name} is not currently supported{NC}"
            )
            raise typer.Abort()
