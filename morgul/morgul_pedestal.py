import contextlib
import datetime
import glob
import time
from logging import getLogger
from pathlib import Path
from typing import Annotated, List, NamedTuple, Optional

import h5py
import numpy
import numpy.typing
import tqdm
import typer

from .config import Detector, get_detector, get_module_info
from .util import BOLD, NC, B, G, R, elapsed_time_string

logger = getLogger(__name__)


def average_pedestal(
    gain_mode: int,
    dataset: h5py.Dataset,
    *,
    parent_progress: tqdm.tqdm | None = None,
    progress_title: str | None = None,
) -> tuple[
    numpy.typing.NDArray, numpy.typing.NDArray, numpy.typing.NDArray[numpy.bool]
]:
    s = dataset.shape
    image = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)
    n_obs = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.uint32)
    image_sq = numpy.zeros(shape=(s[1], s[2]), dtype=numpy.float64)

    # Handle gain mode 2 being ==3
    real_gain_mode = GAIN_MODE_REAL[gain_mode]

    for j in tqdm.tqdm(
        range(s[0]), desc=progress_title or f"Gain Mode {gain_mode}", leave=False
    ):
        i = dataset[j]
        gain = numpy.right_shift(i, 14)
        i = numpy.bitwise_and(i, 0x3FFF)
        valid = gain == real_gain_mode
        i = i.astype(numpy.float64) * valid
        n_obs += valid
        image += i
        image_sq += numpy.square(i)

        if parent_progress:
            parent_progress.update(1)

    # cope with zero valid observations
    assert (
        numpy.sum(n_obs) > 0
    ), f"Error: Got completely blank pedestal in {progress_title}"

    mask = n_obs == 0
    n_obs[n_obs == 0] = 1

    mean = image / n_obs
    variance = (image_sq / n_obs) - numpy.square(mean)
    return mean, variance, mask


class PedestalData(NamedTuple):
    """Pull together data about a particular file and what it represents"""

    filename: Path
    row: int
    col: int
    exptime: float
    gainmode: str
    timestamp: datetime.datetime
    module_serial_number: str
    module_position: str | None
    num_images: int
    data: numpy.typing.NDArray

    @classmethod
    def from_h5(
        cls, filename: Path, h5: h5py.Dataset, detector: Detector
    ) -> "PedestalData":
        # Work out what the module serial number and "position" is
        module = get_module_info(detector, col=h5["column"][()], row=h5["row"][()])

        return PedestalData(
            filename,
            row=h5["row"][()],
            col=h5["column"][()],
            exptime=h5["exptime"][()],
            gainmode=h5["gainmode"][()].decode(),
            timestamp=datetime.datetime.fromtimestamp(h5["timestamp"][()]),
            module_serial_number=module["module"],
            module_position=module.get("position"),
            num_images=h5["data"].shape[0],
            data=h5["data"],
        )


# Mapping from gain mode string to numeric gain mode
GAIN_MODES = {
    "dynamic": 0,
    "forceswitchg1": 1,
    "forceswitchg2": 2,
}
# The "Real" gain mode, as stored in the data
GAIN_MODE_REAL = {0: 0, 1: 1, 2: 3}


def write_pedestal_output(
    root: h5py.Group, pedestal_data: dict[tuple[int, int], dict[int, PedestalData]]
) -> None:
    """Calculate pedestals from source files and write into the output file"""

    # Calculate how many images total
    num_images_total = 0
    for modes in pedestal_data.values():
        for data in modes.values():
            num_images_total += data.num_images

    # Analyse the pedestal data and write the output
    with tqdm.tqdm(total=num_images_total, leave=False) as progress:
        for (col, row), modes in pedestal_data.items():
            for gain_mode, data in sorted(modes.items(), key=lambda x: x[0]):
                pedestal_mean, pedestal_variance, pedestal_mask = average_pedestal(
                    gain_mode,
                    data.data,
                    parent_progress=progress,
                    progress_title=f" {data.module_serial_number} Gain {gain_mode}",
                )
                if data.module_serial_number not in root:
                    group = root.create_group(data.module_serial_number)
                    if data.module_position is not None:
                        group.attrs["position"] = data.module_position.strip("\"'")
                    group.attrs["row"] = row
                    group.attrs["col"] = col

                group = root[data.module_serial_number]
                dataset = group.create_dataset(
                    f"pedestal_{gain_mode}", data=pedestal_mean
                )
                dataset.attrs["timestamp"] = int(data.timestamp.timestamp())
                dataset.attrs["filename"] = str(data.filename)
                dataset = group.create_dataset(
                    f"pedestal_{gain_mode}_variance", data=pedestal_variance
                )
                dataset = group.create_dataset(
                    f"pedestal_{gain_mode}_mask", data=pedestal_mask
                )


def pedestal(
    pedestal_runs: Annotated[
        List[Path],
        typer.Argument(
            help="Data files containing pedestal runs, or a folder containing h5 files for the pedestal runs. There should be a pedestal run for every gain mode."
        ),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "-o",
            help="Name for the output HDF5 file. Default: <detector>_<exptime>ms_pedestal.h5",
        ),
    ] = None,
):
    """
    Calibration setup for Jungfrau
    """
    start_time = time.monotonic()
    detector = get_detector()
    print(f"Using detector: {G}{detector.value}{NC}")

    # Cache all the data
    pedestal_data: dict[tuple[int, int], dict[int, PedestalData]] = {}

    exposure_time: float | None = None

    file_timestamps: set[float] = set()

    # Expand any arguments passed through with wildcards
    expanded_runs: list[Path] = []
    for filename in pedestal_runs:
        if filename.is_dir():
            expanded_runs.extend(filename.glob("*.h5"))
        if "*" in str(filename):
            print(filename)
            expanded_runs.extend(Path(x) for x in glob.glob(str(filename)))

    if not expanded_runs:
        assert False, str(pedestal_runs)

    with contextlib.ExitStack() as stack:
        # Open all pedestal files and validate we don't have any duplicate data
        for filename in expanded_runs:
            logger.debug(f"Reading {filename}")
            h5 = stack.enter_context(h5py.File(filename, "r"))
            data = PedestalData.from_h5(filename, h5, detector)

            file_timestamps.add(h5["timestamp"][()])
            gain_mode = GAIN_MODES[data.gainmode]
            if exposure_time is None:
                exposure_time = data.exptime
                logger.info(
                    f"Generating pedestals for exposure time: {G}{exposure_time*1000:g}{NC} ms"
                )
            else:
                # Validate that this file matches the previously determined exposure time
                if data.exptime != exposure_time:
                    logger.error(
                        f"Error: pedestal file {filename} exposure time ({data.exptime}) does not match others ({exposure_time})"
                    )
                    raise typer.Abort()
            module = pedestal_data.setdefault((data.col, data.row), dict())
            # Validate we didn't get passed two from the same mode
            if gain_mode in module:
                logger.error(
                    f"{BOLD}{R}Error: Duplicate gain mode {gain_mode} (both {module[gain_mode].filename} and {filename}{NC})"
                )
                raise typer.Abort()
            module[gain_mode] = data
            logger.info(
                f"Got file {B}{filename}{NC} with gain mode {G}{gain_mode}{NC} for module ({G}{data.row}{NC}, {G}{data.col}{NC}) ({G}{data.module_serial_number}{NC})"
            )

        # Validate that every module had a complete set of gain modes
        for module_addr, gains in pedestal_data.items():
            if not len(gains) == len(GAIN_MODES):
                logger.error(
                    f"{R}Error: Incomplete data set. Module {module_addr} only has {len(gains)} gain modes, expected {len(GAIN_MODES)}{NC}"
                )
                raise typer.Abort()

        # Work out a timestamp name
        timestamp_name = datetime.datetime.fromtimestamp(
            sorted(file_timestamps)[0]
        ).strftime("%Y-%m-%d_%H-%M-%S")
        output = output or Path(
            f"{detector.value}_{exposure_time*1000:.0f}ms_{timestamp_name}_pedestal.h5"
        )
        with h5py.File(output, "w") as f_output:
            write_pedestal_output(f_output, pedestal_data)
            # Write extra metadata into the file
            f_output.create_dataset("exptime", data=exposure_time)

        print()
        logger.info(
            f"Written output file {B}{output}{NC} in {elapsed_time_string(start_time)}."
        )
