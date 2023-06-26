import logging
from typing import Annotated

import typer

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
    ] = config.Detector.JF1MD,
) -> None:
    # Currently, a choice of context or config function
    obj = ctx.ensure_object(dict)
    obj["detector"] = detector
    config._DETECTOR = detector

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, format="%(message)s"
    )
    logging.debug("Verbose output enabled")


app.command()(morgul_gainmap.gainmap)
app.command()(morgul_pedestal.pedestal)
app.command()(morgul_mask.mask)
app.command()(morgul_correct.correct)
try:
    # view depends on things that might not be installed e.g. napari
    from .view import view

    app.command()(view)
except ModuleNotFoundError:
    pass
app.command()(morgul_watch.watch)
app.command()(morgul_pedestal.pedestal_fudge)
app.command()(morgul_nxmx.nxmx)


def main() -> None:
    app()
