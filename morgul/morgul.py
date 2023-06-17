import typer

from . import morgul_correct, morgul_gainmap, morgul_mask, morgul_pedestal


class NaturalOrderGroup(typer.core.TyperGroup):
    """Custom grouping class for typer for ordered commands"""

    def list_commands(self, _ctx):
        return self.commands.keys()


app = typer.Typer(
    cls=NaturalOrderGroup,
    no_args_is_help=True,
)

app.command()(morgul_gainmap.gainmap)
app.command()(morgul_mask.mask)
app.command()(morgul_pedestal.pedestal)
app.command()(morgul_correct.correct)


def main() -> None:
    app()
