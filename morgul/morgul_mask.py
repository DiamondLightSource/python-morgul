from pathlib import Path
from typing import Annotated, Optional

import typer


def mask(
    flat: Annotated[
        Optional[Path],
        typer.Option(
            "-f",
            "--flat",
            help="File containing flat-field data, to use for mask calculation",
        ),
    ] = None,
):
    """Prepare a pixel mask from flatfield data"""
    print(f"Running Mask on: {flat}")
