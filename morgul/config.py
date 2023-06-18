from __future__ import annotations

import configparser
import enum
import importlib.resources
import logging
import socket
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy
import numpy.typing

from .util import BOLD, NC, B

logger = logging.getLogger(__name__)


# def get_known_detectors() -> set[str]:
#     """Get a list of known detectors from the configuration"""
#     # Since we don't have a literal detector list, learn by inspection.
#     # We expect every detector listed:
#     # - To have modules sections named "<detname>-<module>"
#     # - For each module to have at least a "module" key
#     config = get_config()
#     modules = [x for x in config if "module" in config[x]]
#     # Now, make a set of everything before the last -
#     return {module.rpartition("-")[0] for module in modules}

# TODO: We used to dynamically generate this. This causes mypy issues,
# so for now just hardcode the detectors (e.g. the one that we know we
# are testing)
# Dynamically create detector
# enum Detector = enum.StrEnum("Detector", [x.upper() for x in get_known_detectors()])


class Detector(enum.StrEnum):
    JF1MD = enum.auto()
    JF4PSI = enum.auto()


_DETECTOR: Detector | None = None


def get_detector() -> Detector:
    """Get the currently selected detector"""
    if _DETECTOR is None:
        raise RuntimeError("Default detector not yet initialised")
    return _DETECTOR


@lru_cache
def get_config():
    """Get the local configuration from the installation directory"""
    configuration = configparser.ConfigParser()
    with importlib.resources.as_file(
        importlib.resources.files("morgul") / "morgul.ini"
    ) as fo:
        configuration.read(fo)
    return configuration


def get_module_info(detector: Detector, col: int, row: int) -> dict[str, Any]:
    """Get metainformation about a module from the detector and position"""
    return get_config()[f"{detector}-{col}{row}"]


@lru_cache
def get_calibration_path(hostname: str | None = None) -> Path:
    """Determine the calibration folder location"""

    hostname = hostname or socket.getfqdn()
    config = get_config()
    candidates = sorted([x for x in config.keys() if hostname.endswith(x)], key=len)
    if not candidates:
        raise RuntimeError(
            f"Could not find configuration section matching hostname {hostname}"
        )
    longest_match = candidates[-1]
    logging.debug(f"Matched configuration section {BOLD}{longest_match}{NC}")
    try:
        return Path(get_config()[longest_match]["calibration"])
    except KeyError as e:
        raise RuntimeError(f"Could not find calibration section: {e}")


@lru_cache
def psi_gain_maps(detector: Detector) -> dict[str, numpy.typing.NDArray[numpy.float64]]:
    """Read gain maps from installed location, return as 3 x numpy array g0, g1, g2"""
    config = get_config()
    calib = get_calibration_path()
    print(f"Reading gain maps from: {B}{calib}{NC}")
    result = {}
    modules = [x for x in config.keys() if x.startswith(detector)]
    for k in modules:
        module = config[k]["module"]
        gain_file = list(calib.joinpath(f"{module}_fullspeed").glob("*.bin"))
        assert len(gain_file) == 1
        shape = 3, 512, 1024
        count = shape[0] * shape[1] * shape[2]
        gains = numpy.fromfile(
            open(gain_file[0], "r"), dtype=numpy.float64, count=count
        ).reshape(*shape)
        result[module] = gains

    if not result:
        raise RuntimeError(f"Got no gain map results for detector {detector}")

    return result
