import asyncio
import json
from pathlib import Path

from rich.console import RenderableType
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Footer, LoadingIndicator, Static

data = json.loads(Path("watch_example.json").read_text())
COLUMNS = [
    ("Timestamp", 19),
    ("Filename", None),
    ("Mode", 13),
    ("Exposure", 8),
    ("Images", 6),
]


class DataScreen(Screen):
    CSS = """
    DataTable#header {
        height: 1;
        padding: 0 1;
    }
    DataTable.data {
        border: heavy blue;
        border-title-style: bold;
        border-title-color: white;
    }
    DataTable.active {
        border-bottom: blank;
    }
    """

    _header: DataTable

    def compose(self) -> ComposeResult:
        yield DataTable(id="header")
        # yield DataTable(classes="data")
        yield Footer()
        yield VerticalScroll()

    def on_mount(self) -> None:
        _header: DataTable = self.query_one("#header")
        # _header.add_columns(*COLUMNS)
        for col, size in COLUMNS:
            _header.add_column(col, width=size, key=col)

        self._load_stuff()

    @work
    async def _load_stuff(self):
        _last_parent: Path | None = None
        _table: DataTable | None = None
        scroller = self.query_one(VerticalScroll)

        _longest_filename = 0

        for line, (ts, path, mode, exp, nimage) in enumerate(data):
            if (parent := Path(path).parent) != _last_parent:
                _last_parent = parent
                if _table is not None:
                    _table.remove_class("active")
                _table = DataTable(
                    show_header=False, classes="data active", id=f"table_{line}"
                )
                # _table.add_columns(*COLUMNS)
                for col, size in COLUMNS:
                    _table.add_column(col, width=size, key=col)
                _table.cursor_type = "row"
                _table.border_title = str(parent)
                _table.show_cursor = False
                scroller.mount(_table)

            _longest_filename = max(_longest_filename, len(str(path)))
            _table.add_row(
                *[
                    ts,
                    path,
                    mode,
                    Text(f"{exp:g} ms", justify="right"),
                    Text(str(nimage), justify="right"),
                ],
            )

        # Update column widths
        col: DataTable
        for col in self.query("DataTable"):
            for key in col.columns.keys():
                print(key, key.value)
            col.columns["Filename"].content_width = _longest_filename + 1

        await asyncio.sleep(1.5)
        self.post_message(LoadingScreen.Status("Reading [red]157[/red] files"))
        print("Finished loading")
        self.refresh()
        scroller.scroll_to(None, scroller.max_scroll_y, animate=False)
        await asyncio.sleep(1.5)
        self.post_message(LoadingScreen.FinishedLoading())

    def on_resize(self, message) -> None:
        print("Got data table resize")


class LoadingScreen(Screen):
    CSS = """
    Screen {
        align: center middle;
        layers: bottom top;
    }
    Static {
        content-align: center middle;
        text-align: center;
        layer: top;
        offset: 0 -100%;
    }
    LoadingIndicator {
        layer: bottom;
    }
    """

    class FinishedLoading(Message):
        pass

    class Status(Message):
        def __init__(self, message: RenderableType):
            super().__init__()
            self.message = message

    def set_message(self, message: RenderableType) -> None:
        self.query_one("#message").update(message)

    def compose(self) -> ComposeResult:
        yield Static("Running initial scan", id="message")
        yield Static("")
        yield LoadingIndicator()


class WatchApp(App):
    def on_mount(self) -> None:
        # self.dark = False
        self.push_screen(DataScreen())
        self.push_screen(LoadingScreen())

    def on_loading_screen_finished_loading(
        self, _message: LoadingScreen.FinishedLoading
    ) -> None:
        if isinstance(self.screen, LoadingScreen):
            self.pop_screen()

    def on_loading_screen_status(self, message: LoadingScreen.Status) -> None:
        if isinstance(self.screen, LoadingScreen):
            self.screen.set_message(message.message)


app = WatchApp()
if __name__ == "__main__":
    app.run()
