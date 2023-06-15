import typer

from . import morgul_gainmap, morgul_prepare

app = typer.Typer(add_completion=False)

app.command()(morgul_gainmap.gainmap)
app.command()(morgul_prepare.prepare)
# app.command()(morgul_correct.correct)


def main() -> None:
    app()
