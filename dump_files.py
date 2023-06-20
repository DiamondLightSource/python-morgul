import datetime
import itertools
import os
from pathlib import Path
from typing import Annotated, Optional

import h5py
import typer


def main(
    target_folders: list[Path], root: Annotated[Optional[Path], typer.Option()] = None
):
    if root is None and "VISIT_DATA_ROOT" in os.environ:
        root = Path(os.environ["VISIT_DATA_ROOT"])
        print(f"Using as data root: {root}")

    errors = []
    entries: dict[datetime.datetime, dict] = {}
    for filename in itertools.chain(*[x.glob("**/*.h5") for x in target_folders]):
        try:
            with h5py.File(filename, "r") as f:
                if "timestamp" not in f:
                    print(
                        f"\033[33mWarning: Cannot read {filename} as no timestamp\033[0m"
                    )
                    continue
                timestamp = datetime.datetime.fromtimestamp(f["timestamp"][()])
                # Assume timestamp is unique per collection
                if timestamp in entries:
                    if filename.name > entries[timestamp]["path"].name:
                        continue
                exptime = f["exptime"][()]

                if root:
                    filename = filename.relative_to(root)
                else:
                    root = Path(*filename.parts[:6])
                    filename = filename.relative_to(root)

                entries[timestamp] = {
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "path": filename,
                    "exposure": exptime * 1000,
                    "gainmode": f["gainmode"][()].decode(),
                    "nimage": f["data"].shape[0],
                }
        except BaseException as e:
            errors.append((filename, str(e)))

    column_order = ["timestamp", "path", "gainmode", "exposure", "nimage"]
    for _, values in sorted(entries.items(), key=lambda x: x[0]):
        print(", ".join(str(values[x]) for x in column_order))

    if errors:
        print("\033[31mError: Could not read:")
        print("\n".join(f"  - {f}: {e}" for f, e in errors))
        print("\033[0m")


if __name__ == "__main__":
    typer.run(main)
