import logging
import pathlib
import sys
from typing import Annotated

import typer
from rich import print

from . import (
    config,
    morgul_correct,
    morgul_gainmap,
    morgul_mask,
    morgul_nxmx,
    morgul_pedestal,
)
from .watcher import morgul_watch


class NaturalOrderGroup(typer.core.TyperGroup):
    """Custom grouping class for typer for ordered commands"""

    def list_commands(self, _ctx):
        return self.commands.keys()


app = typer.Typer(
    cls=NaturalOrderGroup,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
)


@app.callback()
def common(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("-v", help="Show debug output")] = False,
    detector: Annotated[
        config.Detector,
        typer.Option(
            "-d",
            "--detector",
            help="The detector to run corrections for",
            case_sensitive=False,
        ),
    ] = config.Detector.JF1MD.value,  # type: ignore
) -> None:
    # Currently, a choice of context or config function
    obj = ctx.ensure_object(dict)
    obj["detector"] = detector
    config._DETECTOR = detector

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, format="%(message)s"
    )
    logging.debug("Verbose output enabled")


CALIBRATION = "Calibration and Correction"
UTILITIES = "Utilities"

app.command(rich_help_panel=UTILITIES)(morgul_gainmap.gainmap)
app.command(rich_help_panel=CALIBRATION)(morgul_pedestal.pedestal)
app.command(rich_help_panel=CALIBRATION)(morgul_mask.mask)
app.command(rich_help_panel=CALIBRATION)(morgul_correct.correct)
app.command(rich_help_panel=CALIBRATION)(morgul_nxmx.nxmx)

try:
    # view depends on things that might not be installed e.g. napari
    from .view import view

    app.command(rich_help_panel=UTILITIES)(view)
except ModuleNotFoundError:

    @app.command(rich_help_panel=UTILITIES)
    def view(filenames: list[pathlib.Path]) -> None:
        """[s]View Jungfrau raw and intermediate data files.[/s] Requires napari module to be installed."""
        print(
            "[red]Error: Cannot view files without [b]napari[/b] module present. Please install it into your environment.[/red]"
        )
        sys.exit(1)


app.command(rich_help_panel=UTILITIES)(morgul_watch.watch)
app.command(rich_help_panel=UTILITIES)(morgul_pedestal.pedestal_fudge)


def main() -> None:
    app()
