import datetime
import logging
import os
import time
from pathlib import Path
from typing import Annotated, Any

import dateutil.tz as tz
import h5py
import typer
import signal
import sys


def _sigpipe_handler(e):
    logger.error("Got sigpipe error")


signal.signal(signal.SIGPIPE, _sigpipe_handler)

from watcher.watcher import Watcher

logger = logging.getLogger(__name__)

# Only consider files matching
FILTER_REGEX = r".+\.h5"
# A cache file so that we can quickly re-present results
CACHE_FILE = ".watcher_history"
# Time to sleep between scans
SLEEP_TIME = 5


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


def main(
    verbose: Annotated[bool, typer.Option("-v", help="Verbose logging")] = False,
    logfile: Annotated[Path, typer.Option(help="Output log file")] = "watching.log",
    plain: Annotated[bool, typer.Option(help="Plain (no fzf) output")] = False,
    root_path: Annotated[
        Path,
        typer.Argument(
            metavar="PATH",
            help="Path to watch. Defaults to environment VISIT_DATA_ROOT",
        ),
    ] = os.environ["VISIT_DATA_ROOT"],
):
    # Set up the logging. Nothing to stdout unless we asked for verbose.
    # logger_dest = {} if verbose else {"filename": logfile}
    logger_dest = {"filename": logfile}
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        level=logging.DEBUG if verbose else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
        **logger_dest,
    )
    logging.getLogger("watcher").setLevel(logging.INFO)

    logger.debug(f"Starting watch on {root_path}")
    watcher = Watcher(root_path)

    # Keep track of files we couldn't open yet, with a timestamp so we don't get stuck
    unscanned_files: set[Path] = set()
    last_folder: Path | None = Path
    longest_path = 0

    while True:
        new_files, dropped_paths = watcher.scan()
        scan_time = time.monotonic()
        # if not new_files and not dropped_paths:
        #     logger.debug("No files, sleeping")
        #     time.sleep(SLEEP_TIME)
        #     continue

        # if not new_files:
        #     continue

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

            except IOError:
                unscanned_files.add(filename)
                continue
            # See if we need to update the "longest path"
            try:
                longest_path = max(
                    longest_path or 0,
                    *[
                        len(str(p.relative_to(root_path)))
                        for p in new_files
                        if len(str(p.relative_to(root_path))) <= 90
                    ],
                )
                logger.debug(f"Longest path is now: {longest_path}")

            except TypeError:
                # This is fragile to missing paths
                pass

            # for ts, missed_file in list(unscanned_files.items()):
            #     if missed_file == filename:
            #         del unscanned_files[ts]

        # For now, just emit the lines
        for data in sorted(processed, key=lambda x: x["timestamp"]):
            filename = data["filename"]
            # Handle unicode prettiness
            prefix = "┃"
            if filename.parent != last_folder:
                if last_folder is not None:
                    # Tie it off
                    if not plain:
                        print(
                            (" " if sys.stdout.isatty() else "- ")
                            + "┗"
                            + "━" * 21
                            + "┷"
                            + "━" * (longest_path + 27)
                            + "┛"
                        )
                prefix = "┏"
                last_folder = filename.parent

            dec = ["" if sys.stdout.isatty() else str(data["filename"].resolve())]
            if not plain:
                dec.append(prefix)
            print(
                " ".join(
                    [
                        *dec,
                        data["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        "│" if not plain else "",
                        str(data["filename"].relative_to(root_path)).ljust(
                            longest_path
                        ),
                        data["gainmode"].ljust(13),
                        f"{data['exptime']*1000:4g}ms",
                        str(data["nimage"]).ljust(5),
                    ]
                )
            )
        time.sleep(SLEEP_TIME)

    # print(new_files)


if __name__ == "__main__":
    typer.run(main)
