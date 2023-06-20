import enum
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeAlias

import h5py
import napari
import numpy as np
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

    points = []
    point_texts = []
    for module in modules:
        for mode in 0, 1, 2:
            name = f"pedestal_{mode}"
            if name in root[module]:
                h, w = root[module][name].shape
                # Get the position for this module
                module_info = config.get_module_from_id(module)
                translate = [0, 0]
                point_vertical = -h - 20
                if module_info["position"] == "bottom":
                    translate[0] = h + 36
                    point_vertical = h + 36 + 20
                translate[1] = mode * (w + 20)
                viewer.add_image(
                    root[module][name][()],
                    name=f"{module}/{mode}",
                    translate=translate,
                    scale=(-1, 1),
                )
                points.append([point_vertical, mode * (w + 20) + (w / 2)])
                point_texts.append(f"{module}/{mode}")
    # Convert the pointsdata to array, and add
    point_data = np.array(points)
    viewer.add_points(point_data, text=point_texts, size=0)

    viewer.reset_view()


@viewer(FileKind.CORRECTED)
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
