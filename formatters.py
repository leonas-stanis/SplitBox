from datetime import datetime


def format_clock(milliseconds: int | None, show_ms: bool = True) -> str:
    if milliseconds is None:
        return "—"

    total = max(0, int(milliseconds))
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)

    suffix = f".{millis:03d}" if show_ms else ""
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}{suffix}"
    return f"{minutes:02d}:{seconds:02d}{suffix}"


def format_delta(milliseconds: int) -> str:
    sign = "−" if milliseconds < 0 else "+"
    return f"{sign}{format_clock(abs(int(milliseconds)))}"


def format_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d %b %Y, %H:%M")
