import re
import time

BOLD = "\033[1m"
R = "\033[31m"
G = "\033[32m"
B = "\033[34m"
NC = "\033[0m"


def elapsed_time_string(start_time: float) -> str:
    elapsed_time = time.monotonic() - start_time
    if elapsed_time > 60:
        return f"{G}{elapsed_time//60:.0f}m {elapsed_time%60:.0f}s{NC}"
    else:
        return f"{G}{elapsed_time:.1f}s{NC}"


def strip_escapes(input: str) -> str:
    return re.sub("\033" + r"\[[\d;]+m", "", input)
