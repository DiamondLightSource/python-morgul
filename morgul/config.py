from __future__ import annotations

import configparser
import importlib.resources
import logging
import socket
from functools import lru_cache
from pathlib import Path

import numpy
import numpy.typing

logger = logging.getLogger(__name__)

BOLD = "\033[1m"
NC = "\033[1m"


@lru_cache
def get_config():
    """Get the local configuration from the installation directory"""
    configuration = configparser.ConfigParser()
    with importlib.resources.as_file(
        importlib.resources.files("morgul") / "morgul.ini"
    ) as fo:
        configuration.read(fo)
    return configuration


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


def psi_gain_maps(detector: str) -> dict[str, numpy.typing.NDArray[numpy.float64]]:
    """Read gain maps from installed location, return as 3 x numpy array g0, g1, g2"""

    config = get_config()
    calib = get_calibration_path()
    result = {}
    for k in config.keys():
        if k.startswith(detector):
            module = config[k]["module"]
            gain_file = list(calib.joinpath(f"M{module}_fullspeed").glob("*.bin"))
            assert len(gain_file) == 1
            shape = 3, 512, 1024
            count = shape[0] * shape[1] * shape[2]
            gains = numpy.fromfile(
                open(gain_file[0], "r"), dtype=numpy.float64, count=count
            ).reshape(*shape)
            result[f"M{module}"] = gains
    return result
