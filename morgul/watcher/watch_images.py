from pathlib import Path
from typing import Annotated

import typer


def watch_images(
    image_root: Annotated[Path, typer.Argument(help="Root of image folders to watch")],
    image_watch_depth: Annotated[
        int,
        typer.Option(
            "--depth",
            help="Folder depth for which to expect new images. Anything deeper than this from the image root might not be noticed.",
        ),
    ] = 2,
    database: Annotated[
        Path,
        typer.Option("--db", help="Image database to update"),
    ] = Path("images.toml"),
):
    """Continuously watch a folder for new images, and log the metadata"""
    pass


def main():
    typer.run(watch_images)


if __name__ == "__main__":
    main()
