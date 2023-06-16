import typer

from . import morgul_correct, morgul_gainmap, morgul_prepare


class NaturalOrderGroup(typer.core.TyperGroup):
    """Custom grouping class for typer for ordered commands"""

    def list_commands(self, _ctx):
        return self.commands.keys()


app = typer.Typer(
    cls=NaturalOrderGroup,
    no_args_is_help=True,
)

app.command()(morgul_gainmap.gainmap)
app.command()(morgul_prepare.prepare)
app.command()(morgul_correct.correct)


def main() -> None:
    app()
