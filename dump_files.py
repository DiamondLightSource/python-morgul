import datetime
import itertools
from pathlib import Path

import h5py
import typer


def main(target_folders: list[Path]):
    entries: dict[datetime.datetime, dict] = {}
    for filename in itertools.chain(*[x.glob("**/*.h5") for x in target_folders]):
        with h5py.File(filename, "r") as f:
            timestamp = datetime.datetime.fromtimestamp(f["timestamp"][()])
            # Assume timestamp is unique per collection
            if timestamp in entries:
                if filename.name > entries[timestamp]["path"].name:
                    continue
            exptime = f["exptime"][()]
            entries[timestamp] = {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "path": filename,
                "exposure": exptime * 1000,
                "gainmode": f["gainmode"][()].decode(),
                "nimage": f["data"].shape[0],
            }

    column_order = ["timestamp", "path", "gainmode", "exposure", "nimage"]
    for _, values in sorted(entries.items(), key=lambda x: x[0]):
        print(", ".join(str(values[x]) for x in column_order))


if __name__ == "__main__":
    typer.run(main)
