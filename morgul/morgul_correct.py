import contextlib
import logging
import time
from pathlib import Path
from typing import Annotated, Any, Optional, cast, overload

import h5py
import hdf5plugin
import numpy
import numpy.typing
import tqdm
import typer

from .config import (
    Detector,
    get_detector,
    get_known_modules_for_detector,
    get_module_info,
    psi_gain_maps,
)
from .util import NC, B, G, R, Y, elapsed_time_string, strip_escapes

logger = logging.getLogger(__name__)


class PedestalCorrections:
    """
    Read in pedestal correction files, and make it easy to retrieve the data
    """

    detector: Detector
    filename: Path
    _tables: dict[tuple[float, str, int], numpy.typing.NDArray]

    def __init__(self, detector: Detector, filename: Path):
        self.detector = detector
        self.filename = filename

        valid_modules = get_known_modules_for_detector(detector)
        assert valid_modules
        self._tables = {}
        with h5py.File(filename, "r") as f:
            # For now, just read all data into memory
            exposure_time = f["exptime"][()]
            for mod in [x for x in valid_modules if x in f]:
                # Read any gain-mode pedestals out of this file
                for gainmode in range(3):
                    if f"pedestal_{gainmode}" in f[mod]:
                        self._tables[exposure_time, mod, gainmode] = numpy.copy(
                            f[mod][f"pedestal_{gainmode}"]
                        )

    @property
    def exposure_times(self):
        return set(x for x, _, _ in self._tables)

    def get_pedestal(
        self, exposure_time: float, module: str, gain_mode: int
    ) -> numpy.typing.NDArray:
        try:
            return self._tables[exposure_time, module, gain_mode]
        except KeyError:
            raise KeyError(
                f"No pedestal data for (exposure: {exposure_time}, module: {module}, mode: {gain_mode})"
            )

    def has_pedestal(
        self, exposure_time: float, module: str, gain_mode: int | None = None
    ) -> bool:
        """Do we contain the pedestal correction tables for a specific module?"""
        if gain_mode is not None:
            return (exposure_time, module, gain_mode) in self._tables
        else:
            # Only say yes if we have all pedestal data (which should always be
            # true - we should never generate a file without all three)
            matches = [
                g for t, m, g in self._tables if t == exposure_time and m == module
            ]
            assert len(matches) == 3, f"Expected 3 pedestal maps, got {len(matches)}"
            return True

    def get_pedestals_dict(
        self, exposure_time: float, module: str
    ) -> dict[str, numpy.typing.NDArray]:
        pass

    @overload
    def __getitem__(
        self, key: float | tuple[float]
    ) -> dict[str, dict[int, numpy.typing.NDArray]]:
        pass

    @overload
    def __getitem__(self, key: tuple[float, str]) -> dict[int, numpy.typing.NDArray]:
        pass

    @overload
    def __getitem__(self, key: tuple[float, str, int]) -> numpy.typing.NDArray:
        pass

    def __getitem__(
        self, key: float | tuple[float] | tuple[float, str] | tuple[float, str, int]
    ):
        output: Any = {}
        if isinstance(key, float):
            key = (key,)
        if len(key) == 1:
            # Get all entries for one exposure time
            for module, gainmode in [(m, g) for e, m, g in self._tables if e == key[0]]:
                output.setdefault(module, dict())[gainmode] = self._tables[
                    key[0], module, gainmode
                ]
        elif len(key) == 2:
            # Get all entries for one exposure time
            key = cast(tuple[float, str], key)
            for gainmode in [
                g for e, m, g in self._tables if e == key[0] and m == key[1]
            ]:
                # output.setdefault(module, dict())[gainmode] = self._tables(key, module, gainmode)
                output[gainmode] = self._tables[key[0], key[1], gainmode]
        elif len(key) == 3:
            # assert isinstance(key, tuple)
            return self._tables[cast(tuple[float, str, int], key)]
        return output


class Masker:
    filename: Path
    exposure_times: set[float]

    def __init__(self, detector: Detector, filename: Path):
        self.filename = filename
        modules = get_known_modules_for_detector(detector)

        self._table = {}

        # Read the masks out of this data file
        with h5py.File(filename, "r") as f:
            exptime = f["exptime"][()]
            self.exposure_times = {exptime}
            for module in modules:
                if module in f:
                    self._table[exptime, module] = numpy.copy(f[module]["mask"])

    def __getitem__(self, key: tuple[float, str]) -> numpy.typing.NDArray:
        return self._table[key]

    def __contains__(self, key: tuple[float, str]) -> bool:
        return key in self._table


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


def correct_frame(
    raw: numpy.typing.NDArray[numpy.uint16],
    pedestals: dict[int, numpy.typing.NDArray],
    g012,
    energy: float,
    mask: numpy.typing.NDArray | None = None,
):
    """Correct pixel values to photons in frame"""

    if mask is None:
        mask = numpy.full(raw.shape, False, dtype=bool)

    assert 1 in pedestals and 2 in pedestals and 0 in pedestals

    gain = numpy.right_shift(raw, 14)

    mask = mask == False
    m0 = (pedestals[0] != 0) * mask
    frame = ((gain == 0) * (numpy.bitwise_and(raw, 0x3FFF)) * m0 - pedestals[0]) / (
        g012[0] * energy
    )

    if 1 in pedestals:
        m1 = (pedestals[1] != 0) * mask
        frame += (
            (gain == 1) * ((numpy.bitwise_and(raw, 0x3FFF)) * m1 - pedestals[1])
        ) / (g012[1] * energy)

    if 2 in pedestals:
        m2 = (pedestals[2] != 0) * mask
        frame += (
            (gain == 3) * ((numpy.bitwise_and(raw, 0x3FFF)) * m2 - pedestals[2])
        ) / (g012[2] * energy)
    return frame


def output_filename(filename: Path, output_dir: Path | None) -> Path:
    # Work out where the output file will go
    return (
        output_dir or filename.parent
    ) / f"{filename.stem}_corrected{filename.suffix}"


def datafile_prechecks(
    data_files: list[Path], force: bool, output_dir: Path, stack: contextlib.ExitStack
) -> dict[Path, h5py.File]:
    """Open data files, and do basic pre-correction sanity checks"""
    # Do a pre-pass so that we can count the total number of images
    h5s = {}
    total_images = 0
    existing_output_filenames = []
    # Go through every data file input on a first pass
    for filename in data_files:
        h5 = stack.enter_context(h5py.File(filename, "r"))
        # If this file is already corrected, ignore it
        if "data" not in h5:
            logger.error(f"{R}Error: File {filename} does not have a 'data' dataset")
            raise typer.Abort()
        # If this was previously corrected, ignore it
        if "corrected" in h5["data"].attrs and h5["data"].attrs["corrected"]:
            logger.warning(f"{Y}File {filename} contains corrected data, ignoring.{NC}")
            h5.close()
            continue
        total_images += h5["data"].shape[0]
        h5s[filename] = h5
        # Work out what the output filename would be
        out = output_filename(filename, output_dir)
        if out.is_file():
            existing_output_filenames.append(out)

    # Handle output filename existence. Do this so that we print everything
    # that could be overwritten, instead of the first - in which case it
    # might unexpectedly overwrite a file the user didn't expect
    if existing_output_filenames and not force:
        outputs = "\n".join(["  - " + str(x) for x in existing_output_filenames])
        logger.error(
            f"""
{R}Error: The following files already exist and would be overwritten:

{outputs}

please pass --force/-f if you want to overwrite these files.{NC}
"""
        )
        raise typer.Abort()

    if not h5s:
        logger.error(
            f"{R}Error: No data files present after filtering out corrected{NC}"
        )
        raise typer.Abort()

    return h5s


def correct(
    pedestal: Annotated[
        Path,
        typer.Argument(
            help="Pedestal data file for the module(s), from 'morgul pedestal'."
        ),
    ],
    mask_file: Annotated[Path, typer.Argument(help="Pixel mask, from 'morgul mask'.")],
    data_files: Annotated[
        list[Path], typer.Argument(help="Data files, for corrections.", metavar="DATA")
    ],
    energy: Annotated[
        float, typer.Option("-e", "--energy", help="photon energy (keV)")
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "-o",
            help="Output folder for the corrected files. Files will be written here with the suffix '_corrected.<ext>'. Defaults to same as input file. ",
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Overwrite files that already exist")
    ] = False,
):
    """Correction program for Jungfrau"""

    start_time = time.monotonic()
    detector = get_detector()
    logger.info(f"Using detector: {G}{detector.value}{NC}")

    logger.info(f"Using mask from: {B}{mask_file}{NC}")
    masker = Masker(detector, mask_file)

    pedestals = PedestalCorrections(detector, pedestal)
    logger.info(f"Reading pedestals from: {B}{pedestal}{NC}")

    gain_maps = psi_gain_maps(detector)

    available_exposures = pedestals.exposure_times & masker.exposure_times

    with contextlib.ExitStack() as stack:
        # Do basic cross-checks and filter out corrected files
        h5s = datafile_prechecks(data_files, force, output, stack)

        total_images = sum(x["data"].shape[0] for x in h5s.values())
        print(f"Correcting total of: {G}{total_images}{NC} images")

        # Do validations for everything before we start correcting
        for filename, h5 in h5s.items():
            # Validate we can process this timestamp
            if (exptime := h5["exptime"][()]) not in available_exposures:
                available_str = ", ".join(f"{x*1000:g}ms" for x in available_exposures)
                logger.error(
                    f"{R}Error: {filename} is exposure {exptime*1000:g} ms, only: {available_str} available."
                )
            # Validate that the file is dynamic
            if not (gainmode := h5["gainmode"][()].decode()) == "dynamic":
                logger.error(f"{R}Error: {filename} is '{gainmode}', not 'dynamic'{NC}")
                raise typer.Abort()

        # Start the correction/output process
        progress = stack.enter_context(tqdm.tqdm(total=total_images, leave=False))
        for filename, h5 in h5s.items():
            # Get the module this data was taken with
            module = get_module_info(detector, h5["column"][()], h5["row"][()])[
                "module"
            ]

            data = h5["data"]
            exposure_time = h5["exptime"][()]

            # Check we have a mask for this module
            if (exposure_time, module) not in masker:
                logger.error(
                    f"{R}Error: Do not have mask for (exptime: {exposure_time*1000:g} ms, module: {module}){NC}"
                )
                raise typer.Abort()

            out_filename = output_filename(filename, output)
            pre_msg = f"Processing {G}{data.shape[0]}{NC} images from module {G}{module}{NC} in "
            progress.write(
                f"{pre_msg}{B}{filename}{NC}\n{' '*(len(strip_escapes(pre_msg))-5)}into {B}{out_filename}{NC}"
            )

            # Safety check - don't overwrite if no --force
            if out_filename.is_file() and not force:
                logger.error(
                    f"{R}Error: {out_filename} exists but will not overwrite. Pass --force to overwrite."
                )
                raise typer.Abort()

            with h5py.File(out_filename, "w") as f:
                out_dataset = f.create_dataset(
                    "data",
                    shape=(data.shape[0], 514, 1030),
                    dtype=numpy.int32,
                    chunks=(1, 514, 1030),
                    **hdf5plugin.Bitshuffle(cname="lz4"),
                )
                out_dataset.attrs["corrected"] = True
                for n in tqdm.tqdm(
                    range(data.shape[0]), leave=False, desc=f"{filename.name}"
                ):
                    frame = correct_frame(
                        data[n],
                        pedestals[exposure_time, module],
                        gain_maps[module],
                        energy,
                        masker[exposure_time, module],
                    )
                    progress.update(1)
                    out_dataset[n] = embiggen(numpy.around(frame))
                # Copy over all other metadata
                for k, v in h5.items():
                    if isinstance(v, h5py.Dataset) and v.shape == ():
                        f.create_dataset(k, data=v)

    print()
    logger.info(
        f"Written {G}{total_images}{NC} images in {G}{len(data_files)}{NC}s corrected data files in {elapsed_time_string(start_time)}."
    )
