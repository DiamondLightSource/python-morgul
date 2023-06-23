import datetime
import logging
import os
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import IO, Annotated, Any

import dateutil.tz as tz
import h5py
import typer

from morgul.watcher.watcher import Watcher

logger = logging.getLogger(__name__)

# Only consider files matching
FILTER_REGEX = r".+\.h5"
# A cache file so that we can quickly re-present results
CACHE_FILE = ".watcher_history"
# Time to sleep between scans
SLEEP_TIME = 5


class Settings:
    root_path: Path

    @classmethod
    @lru_cache
    def get(cls) -> "Settings":
        return cls()


def read_h5_info(filename: Path) -> dict[str, Any] | None:
    with h5py.File(filename, "r") as f:
        if "timestamp" not in f:
            logger.info(f"Skipping file {f} as no timestamp")
            return None
        timestamp = datetime.datetime.fromtimestamp(f["timestamp"][()]).replace(
            tzinfo=tz.UTC
        )
        exptime = f["exptime"][()]

        # # Assume timestamp is unique per collection
        # if timestamp in entries:
        #     if filename.name > entries[timestamp]["path"].name:
        #         continue

        # if root:
        #     filename = filename.relative_to(root)
        # else:
        #     root = Path(*filename.parts[:6])
        #     filename = filename.relative_to(root)

        return {
            "timestamp": timestamp,
            "filename": filename,
            "exptime": exptime,
            "gainmode": f["gainmode"][()].decode(),
            "nimage": f"{f['data'].shape[0]:5}",
        }


class EmitHandler:
    _entries: dict[Path, dict[str, Any]]
    _last_folder: Path | None = None
    _output_stream: IO
    _longest_path: int

    def __init__(self, output_stream: IO = sys.stdout, *, fzf: bool = False):
        self._entries = {}
        self._fzf = fzf
        self._output_stream = output_stream
        self._longest_path = 0

    def set_output_stream(self, stream: IO) -> None:
        self._output_stream = stream

    def print(self, *args, sep: str = " ", end: str = "\n") -> None:
        self._output_stream.write(sep.join(str(x) for x in args) + end)

    def emit_new_entries(self, entries: list[dict[str, Any]]) -> None:
        # Check to see if we need to extend the longest path for these
        self._longest_path = max(
            self._longest_path,
            *[
                len(str(x["filename"].relative_to(Settings.get().root_path)))
                for x in entries
            ],
        )

        path_length = min(self._longest_path, 87)

        for entry in sorted(entries, key=lambda x: x["timestamp"]):
            # For now, just emit the lines
            filename = entry["filename"]
            # Handle unicode prettiness
            prefix = "┃"
            # Handle dividers if our new entry is in a different folder
            if filename.parent != self._last_folder:
                if self._last_folder is not None:
                    # Tie it off
                    self.print(
                        ("- " if self._fzf else "  ")
                        + "┗"
                        + "━" * 21
                        + "┷"
                        + "━" * (path_length + 27)
                        + "┛"
                    )
                prefix = "┏"
                self._last_folder = filename.parent

            dec = [" " if not self._fzf else str(entry["filename"].resolve()), prefix]
            self.print(
                *dec,
                entry["timestamp"].astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                "│",
                str(entry["filename"].relative_to(Settings.get().root_path)).ljust(
                    path_length
                ),
                entry["gainmode"].ljust(13),
                f"{entry['exptime']*1000:4g}ms",
                str(entry["nimage"]).ljust(5),
            )

    def reemit(self) -> None:
        """Print everything again"""
        raise NotImplementedError()


def watch(
    verbose: Annotated[
        int,
        typer.Option(
            "-v", help="Verbose logging. Pass twice to log to stdout.", count=True
        ),
    ] = 0,
    logfile: Annotated[Path, typer.Option(help="Output log file")] = Path(
        "watching.log"
    ),
    plain: Annotated[bool, typer.Option(help="Plain (no fzf) output")] = False,
    root_path: Annotated[
        Path,
        typer.Argument(
            metavar="PATH",
            help="Path to watch. Defaults to environment VISIT_DATA_ROOT",
        ),
    ] = None,
    use_fzf: Annotated[bool, typer.Option("--fzf")] = False,
):
    """Watch a data folder for new files appearing"""

    # This command wants to control logging completely but the root
    # morgul object sets up logging itself, so we want to undo what it
    # did.
    for loghandler in logging.root.handlers[:]:
        logging.root.removeHandler(loghandler)

    # Set up the logging. Nothing to stdout unless we asked for verbose.
    logger_dest = {"filename": logfile} if verbose < 2 else {}
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        level=logging.DEBUG if verbose else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
        **logger_dest,  # type: ignore
    )
    logging.getLogger("morgul.watcher.watcher").setLevel(logging.INFO)

    if root_path is None:
        if "VISIT_DATA_ROOT" in os.environ:
            root_path = Path(os.environ["VISIT_DATA_ROOT"])
        else:
            print(
                "Error: Have not specified root_path and VISIT_DATA_ROOT not set. Please do one of these."
            )
            raise typer.Abort()

    # Update the singleton root object
    Settings.get().root_path = root_path

    logger.debug(f"Starting watch on {root_path}")
    watcher = Watcher(root_path)

    # Keep track of files we couldn't open yet, with a timestamp so we don't get stuck
    unscanned_files: set[Path] = set()

    if not use_fzf:
        print("Doing initial scan, this could take a minute...")

    if use_fzf:
        fzf = subprocess.Popen(
            [
                "fzf",
                "--multi",
                "--tac",
                # "--ansi",
                "--bind",
                "tab:toggle",
                "--with-nth=2..",
                "--phony",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding="utf-8",
        )
        handler = EmitHandler(fzf.stdin, fzf=True)
    else:
        handler = EmitHandler(sys.stdout)

    while True:
        new_files, dropped_paths = watcher.scan()
        scan_time = time.monotonic()

        # Store a list of processed - we may want to group/reorder once we have metadata
        processed = []
        # For each new file, open it and get some details
        for filename in sorted(new_files + list(unscanned_files)):
            try:
                data = read_h5_info(filename)
                if not data:
                    logger.info(f"File {filename} is not a data file")
                    continue
                processed.append(data)
                if filename in unscanned_files:
                    unscanned_files.remove(filename)

            except (IOError, KeyError):
                unscanned_files.add(filename)
                continue

        if processed:
            handler.emit_new_entries(processed)

        if use_fzf:
            try:
                fzf.wait(timeout=SLEEP_TIME)
                fzf_output = fzf.stdout.read()
                logger.info("Output: " + fzf.stdout.read())
                return
            except subprocess.TimeoutExpired:
                pass
        else:
            time.sleep(SLEEP_TIME)

    # If fzf, then we might have gotten something to use


if __name__ == "__main__":
    typer.run(watch)
