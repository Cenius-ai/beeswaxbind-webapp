#!/usr/bin/env python3
"""BeeswaxBind -- offline harness-needle, thread and wax-blend reference.

Three calculators (needle, tension, wax) plus a browsable reference surface, all
driven from tables bundled in this file.  Standard library only, no network
access and nothing written to disk at runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__version__ = "1.0.0"
PROG = "beeswaxbind"

EXIT_OK = 0
EXIT_USAGE = 2

MM_PER_INCH = 25.4
MM_PER_OZ = 0.4
GRAMS_PER_OZ = 28.349523125
MIN_LEATHER_OZ = 2.0
MAX_LEATHER_OZ = 20.0
DEFAULT_LEATHER_OZ = 4.0
DEFAULT_THREAD = "18/3"
DEFAULT_SPI = 6.0
DEFAULT_BATCH_GRAMS = 50.0
DEFAULT_PARTS = "5:1"
LABEL_WIDTH = 16

UNITS_METRIC = "metric"
UNITS_IMPERIAL = "imperial"
UNITS_BOTH = "both"
UNIT_CHOICES = (UNITS_METRIC, UNITS_IMPERIAL, UNITS_BOTH)

TABLE_NAMES = ("threads", "needles", "wax")


class ValidationError(Exception):
    """A user-facing input problem: one stderr line and exit code 2."""

    def __init__(self, field: str, message: str, exit_code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.exit_code = exit_code


# ---------------------------------------------------------------------------
# Bundled reference tables (F5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Thread:
    """A linen thread number and its measured properties."""

    number: str
    ply_count: int
    diameter_mm: float
    breaking_lb: float
    breaking_kg: float
    note: str


@dataclass(frozen=True)
class Needle:
    """A harness needle size with the thread numbers it will carry."""

    name: str
    metric_mm: float
    us_size: str
    length_mm: float
    fits_threads: Tuple[str, ...]


@dataclass(frozen=True)
class WaxRecipe:
    """A named beeswax:rosin thread-wax recipe."""

    preset: str
    beeswax_parts: Fraction
    rosin_parts: Fraction
    use_note: str

    @property
    def ratio_label(self) -> str:
        return "%s:%s" % (_frac_text(self.beeswax_parts), _frac_text(self.rosin_parts))


@dataclass(frozen=True)
class TensionBand:
    """The stitches-per-inch range that reads as standard tension on a leather."""

    low_oz: float
    high_oz: float
    min_spi: float
    max_spi: float


THREADS: Tuple[Thread, ...] = (
    Thread("12/3", 3, 0.86, 20.0, 9.1, "heavy harness seams, strap ends and load-bearing straps"),
    Thread("16/3", 3, 0.75, 17.0, 7.7, "saddle seams, thick strap work and belt loops"),
    Thread("18/3", 3, 0.65, 15.0, 6.8, "everyday leatherwork: bag seams, cases and belts"),
    Thread("18/4", 4, 0.72, 18.0, 8.2, "heavier seams on strap ends and reinforced edges"),
    Thread("25/3", 3, 0.55, 12.0, 5.4, "general leathercraft and thick garment work"),
    Thread("25/4", 4, 0.62, 15.0, 6.8, "reinforced seams on mid-weight leather"),
    Thread("30/3", 3, 0.48, 10.0, 4.5, "fine leatherwork, wallets and small cases"),
    Thread("35/3", 3, 0.42, 8.0, 3.6, "decorative stitching on light leather"),
    Thread("40/3", 3, 0.38, 7.0, 3.2, "linings, edge binding and turned edges"),
    Thread("45/3", 3, 0.35, 6.0, 2.7, "close work on small goods and card cases"),
    Thread("60/3", 3, 0.30, 5.0, 2.3, "glove-weight leather and fine binding"),
    Thread("80/3", 3, 0.25, 4.0, 1.8, "bookbinding and delicate close work"),
)

NEEDLES: Tuple[Needle, ...] = (
    Needle("harness 0", 2.00, "0", 57.0, ("12/3", "16/3", "18/4")),
    Needle("harness 1", 1.80, "1", 54.0, ("12/3", "16/3", "18/4")),
    Needle("harness 2", 1.60, "2", 51.0, ("16/3", "18/3", "18/4", "25/4")),
    Needle("harness 3", 1.40, "3", 48.0, ("18/3", "18/4", "25/3", "25/4")),
    Needle("harness 4", 1.20, "4", 45.0, ("18/3", "25/3", "25/4", "30/3")),
    Needle("harness 5", 1.05, "5", 42.0, ("25/3", "30/3", "35/3")),
    Needle("harness 6", 0.90, "6", 40.0, ("30/3", "35/3", "40/3")),
    Needle("harness 7", 0.80, "7", 38.0, ("35/3", "40/3", "45/3")),
    Needle("harness 8", 0.70, "8", 36.0, ("40/3", "45/3", "60/3")),
    Needle("harness 9", 0.60, "9", 34.0, ("45/3", "60/3", "80/3")),
    Needle("harness 10", 0.50, "10", 32.0, ("60/3", "80/3")),
    Needle("harness 11", 0.45, "11", 30.0, ("80/3",)),
)

WAX_RECIPES: Tuple[WaxRecipe, ...] = (
    WaxRecipe("soft", Fraction(5), Fraction(1), "everyday hand sewing; stays tacky so the thread grips without dragging"),
    WaxRecipe("standard", Fraction(4), Fraction(1), "harness and bag seams worked in a temperate workshop"),
    WaxRecipe("hard", Fraction(3), Fraction(1), "coarse thread and heavy harness; firm finish with little surface tack"),
    WaxRecipe("extra-soft", Fraction(8), Fraction(1), "fine bookbinding thread in warm rooms where wax would set glassy"),
    WaxRecipe("extra-hard", Fraction(2), Fraction(1), "abrasion-heavy saddle seams that want a crisp, dry pull"),
    WaxRecipe("summer", Fraction(6), Fraction(1), "warm-weather blend that keeps tack low in a hot workshop"),
)

TENSION_BANDS: Tuple[TensionBand, ...] = (
    TensionBand(2.0, 5.0, 6.0, 8.0),
    TensionBand(5.0, 8.0, 5.0, 7.0),
    TensionBand(8.0, 12.0, 4.0, 6.0),
    TensionBand(12.0, 16.0, 3.0, 5.0),
    TensionBand(16.0, 20.0, 2.0, 4.0),
)

THREAD_BY_NUMBER: Dict[str, Thread] = {t.number: t for t in THREADS}
PRESET_BY_NAME: Dict[str, WaxRecipe] = {r.preset: r for r in WAX_RECIPES}
CANONICAL_PRESETS = ("soft", "standard", "hard")
KNOWN_THREAD_NUMBERS = ", ".join(t.number for t in THREADS)

# ---------------------------------------------------------------------------
# Presentation tokens (the committed design direction)
#
# Surface: the terminal itself, dark by default.  Type: system monospace.
# Shape: aligned columns and plain '-' rules, no chrome.  One accent - the same
# oklch/hex below - marks the primary pick and the tension verdict, and it is
# never the only signal: the label text carries the meaning too.
# ---------------------------------------------------------------------------

ACCENT_OKLCH = "oklch(0.58 0.12 50)"          # the token, in the form CSS wants
ACCENT_HEX = "#b26232"                          # the same token, for non-CSS consumers
ACCENT_RGB = tuple(int(ACCENT_HEX[index:index + 2], 16) for index in (1, 3, 5))
ACCENT_ANSI = "\x1b[38;2;%d;%d;%dm" % ACCENT_RGB   # truecolor escape, derived from ACCENT_HEX
ACCENT_ANSI_256 = "\x1b[38;5;173m"             # 256-colour fallback for older terminals
RESET_ANSI = "\x1b[0m"
ACCENT_LABELS = ("primary", "verdict")
COLOUR_CHOICES = ("auto", "always", "never")

_COLOUR_ENABLED = False


def _accent_code() -> str:
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return ACCENT_ANSI
    return ACCENT_ANSI_256


def _resolve_colour(mode: str) -> bool:
    """auto colours a real terminal only, so pipes, files and logs stay plain."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def _set_colour(mode: str) -> None:
    global _COLOUR_ENABLED
    _COLOUR_ENABLED = _resolve_colour(mode)


def _highlight(text: str) -> str:
    """Paint the primary pick and the verdict with the single accent colour."""
    code = _accent_code()
    painted = []
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip(" "))
        for label in ACCENT_LABELS:
            if line[indent:].startswith(label + " "):
                line = "%s%s%s%s%s" % (line[:indent], code, label, RESET_ANSI, line[indent + len(label):])
                break
        painted.append(line)
    return "\n".join(painted)


def _render_text(report) -> str:
    """Report text, accented only when colour is switched on for this run."""
    text = report.to_text()
    return _highlight(text) if _COLOUR_ENABLED else text



# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------


def _frac_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return "%g" % float(value)


def fmt_oz(oz: float) -> str:
    """Render an ounce weight without noisy trailing zeros."""
    return "%g oz" % round(oz, 3)


def fmt_mm(mm: float) -> str:
    """A millimetre measure for diameters and leather thicknesses."""
    return "%g mm" % round(mm, 3)


def fmt_size(mm: float) -> str:
    """A needle size in millimetres, always two decimals so sizes line up."""
    return "%.2f mm" % round(mm, 2)


def fmt_inches(mm: float) -> str:
    inches = mm / MM_PER_INCH
    places = 3 if abs(inches) < 0.1 else 2
    return "%.*f in" % (places, inches)


def fmt_measure(mm: float, units: str) -> str:
    """A length in millimetres, inches, or both, honouring the units switch."""
    if units == UNITS_METRIC:
        return "%.2f mm" % round(mm, 2)
    if units == UNITS_IMPERIAL:
        return "%.2f in" % (mm / MM_PER_INCH)
    return "%.2f mm (%.2f in)" % (round(mm, 2), mm / MM_PER_INCH)


def fmt_g(grams: float) -> str:
    rounded = round(grams, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return "%g g" % round(rounded)
    return "%.1f g" % rounded


def fmt_oz_weight(grams: float) -> str:
    return "%.2f oz" % (grams / GRAMS_PER_OZ)


def fmt_weight(grams: float, units: str) -> str:
    if units == UNITS_METRIC:
        return fmt_g(grams)
    if units == UNITS_IMPERIAL:
        return fmt_oz_weight(grams)
    return "%s (%s)" % (fmt_g(grams), fmt_oz_weight(grams))


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Aligned plain-text columns; no colour, no escape sequences."""
    widths = [len(h) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    lines = [
        "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers)).rstrip(),
        "  ".join("-" * widths[i] for i in range(len(headers))),
    ]
    for row in rows:
        lines.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    return "\n".join(lines)


def _line(label: str, value: str) -> str:
    return "  %s%s%s" % (label, " " * max(1, LABEL_WIDTH - len(label)), value)


def _heading(title: str) -> str:
    return "%s\n%s" % (title, "-" * max(len(title), 16))


def _section(title: str, lines: Sequence[str]) -> str:
    return "\n".join([title] + list(lines))


# ---------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------

_MEASURE_RE = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([a-z\"/]*)$")

_OZ_UNITS = ("", "oz", "ounce", "ounces")
_MM_UNITS = ("mm", "millimetre", "millimetres", "millimeter", "millimeters")
_GRAM_UNITS = ("", "g", "gram", "grams", "gm", "gms")
_OZ_UNITS_STRICT = ("oz", "ounce", "ounces")


def _split_measure(text: str, field: str, hint: str) -> Tuple[float, str]:
    raw = (text or "").strip().lower()
    if not raw:
        raise ValidationError(field, hint)
    match = _MEASURE_RE.match(raw)
    if match is None:
        raise ValidationError(field, hint)
    return float(match.group(1)), match.group(2)


def parse_units(text: str) -> str:
    value = (text or "").strip().lower()
    if value not in UNIT_CHOICES:
        raise ValidationError("units", "units must be metric, imperial or both (got '%s')" % (text or ""))
    return value


def parse_thread_number(text: str) -> Thread:
    raw = (text or "").strip().upper().replace(" ", "")
    if not raw:
        raise ValidationError("thread", "a thread number is required, for example 18/3")
    key = raw.replace("-", "/").replace("X", "/")
    thread = THREAD_BY_NUMBER.get(key)
    if thread is None:
        raise ValidationError(
            "thread",
            "unknown thread number '%s'; known thread numbers are %s" % ((text or "").strip(), KNOWN_THREAD_NUMBERS),
        )
    return thread


@dataclass(frozen=True)
class Leather:
    """A leather weight carried in both ounce and millimetre form."""

    oz: float
    mm: float
    source_unit: str
    source_value: float

    def describe(self, units: str) -> str:
        oz_text = fmt_oz(self.oz)
        mm_text = fmt_mm(self.mm)
        if units == UNITS_METRIC:
            return mm_text
        if units == UNITS_IMPERIAL:
            return oz_text
        if self.source_unit == "mm":
            return "%s (%s)" % (mm_text, oz_text)
        return "%s (%s)" % (oz_text, mm_text)


def parse_leather(text: str) -> Leather:
    hint = "leather weight must be a number such as 4oz or 2mm (got '%s')" % (text or "")
    value, unit = _split_measure(text, "leather", hint)
    if unit in _MM_UNITS:
        mm = value
        oz = value * (1.0 / MM_PER_OZ)
    elif unit in _OZ_UNITS:
        oz = value
        mm = value * MM_PER_OZ
    else:
        raise ValidationError("leather", hint)
    if not (MIN_LEATHER_OZ - 1e-9 <= oz <= MAX_LEATHER_OZ + 1e-9):
        raise ValidationError(
            "leather",
            "leather weight must be between 2 and 20 oz (0.8 to 8 mm); got %s oz" % ("%g" % round(oz, 3)),
        )
    return Leather(oz=oz, mm=mm, source_unit=("mm" if unit in _MM_UNITS else "oz"), source_value=value)


def parse_spi(text: str) -> float:
    raw = (text or "").strip().lower()
    if raw.endswith("spi"):
        raw = raw[:-3].strip()
    hint = "spi must be a number such as 6 (got '%s')" % (text or "")
    match = _MEASURE_RE.match(raw)
    if match is None or match.group(2) != "":
        raise ValidationError("spi", hint)
    value = float(match.group(1))
    if value <= 0:
        raise ValidationError("spi", "spi must be greater than 0 (got '%s')" % (text or ""))
    return value


def parse_length(text: str) -> float:
    """A stitch length in millimetres; mm is assumed when no unit is given."""
    hint = "stitch length must be a number such as 4mm or 0.17in (got '%s')" % (text or "")
    value, unit = _split_measure(text, "length", hint)
    if unit in ("in", "inch", "inches", '"'):
        mm = value * MM_PER_INCH
    elif unit in _MM_UNITS:
        mm = value
    else:
        raise ValidationError("length", hint)
    if mm <= 0:
        raise ValidationError("length", "stitch length must be greater than 0 (got '%s')" % (text or ""))
    return mm


def parse_batch_grams(text: str) -> float:
    hint = "batch weight must be a positive number such as 50 or 50g (got '%s')" % (text or "")
    value, unit = _split_measure(text, "batch", hint)
    if unit in _GRAM_UNITS:
        grams = value
    elif unit in _OZ_UNITS_STRICT:
        grams = value * GRAMS_PER_OZ
    else:
        raise ValidationError("batch", hint)
    if grams <= 0:
        raise ValidationError("batch", "batch weight must be greater than zero (got '%s')" % (text or ""))
    return grams


def parse_parts(text: str) -> Tuple[Fraction, Fraction]:
    raw = (text or "").strip()
    pieces = raw.split(":")
    hint = "parts must look like BEESWAX:ROSIN, for example 5:1 (got '%s')" % raw
    if len(pieces) != 2:
        raise ValidationError("parts", hint)
    values = []
    for piece in pieces:
        piece = piece.strip()
        try:
            fraction = Fraction(piece)
        except (ValueError, ZeroDivisionError):
            raise ValidationError("parts", hint)
        values.append(fraction)
    beeswax, rosin = values
    if beeswax <= 0 or rosin <= 0:
        raise ValidationError("parts", "both beeswax and rosin parts must be greater than zero (got '%s')" % raw)
    return beeswax, rosin


def parse_preset(text: str) -> WaxRecipe:
    name = (text or "").strip().lower()
    recipe = PRESET_BY_NAME.get(name)
    if recipe is None:
        raise ValidationError(
            "preset",
            "unknown preset '%s'; known presets are %s" % ((text or "").strip(), ", ".join(PRESET_BY_NAME)),
        )
    return recipe


def parse_table_name(text: str) -> str:
    name = (text or "").strip().lower()
    if name not in TABLE_NAMES:
        raise ValidationError("show", "unknown table '%s'; valid tables are %s" % ((text or "").strip(), ", ".join(TABLE_NAMES)))
    return name

# ---------------------------------------------------------------------------
# Needle and thread recommender (F1)
# ---------------------------------------------------------------------------


def needles_for_thread(thread_number: str) -> List[Needle]:
    return [needle for needle in NEEDLES if thread_number in needle.fits_threads]


def pick_needles(thread: Thread, leather_oz: float) -> Tuple[Needle, Optional[Needle]]:
    """Choose a primary needle plus one alternative that will carry the thread.

    The eye has to clear the thread, so the search starts at the thread
    diameter plus a working allowance that grows slightly with leather weight:
    heavier leather wants a stiffer needle.
    """
    candidates = needles_for_thread(thread.number)
    if not candidates:
        raise ValidationError("thread", "no harness needle in the bundled table fits thread %s" % thread.number)
    target_mm = thread.diameter_mm + 0.60 + 0.02 * leather_oz
    ordered = sorted(candidates, key=lambda n: (abs(n.metric_mm - target_mm), -n.metric_mm))
    primary = ordered[0]
    alternate = ordered[1] if len(ordered) > 1 else None
    return primary, alternate


def needle_size_text(needle: Needle, units: str) -> str:
    if units == UNITS_METRIC:
        return "harness needle %s" % fmt_size(needle.metric_mm)
    if units == UNITS_IMPERIAL:
        return "harness needle US %s" % needle.us_size
    return "harness needle %s (US %s)" % (fmt_size(needle.metric_mm), needle.us_size)


def breaking_strength_text(thread: Thread, units: str) -> str:
    pounds = "%g lb" % thread.breaking_lb
    kilo = "%g kg" % thread.breaking_kg
    if units == UNITS_METRIC:
        return kilo
    if units == UNITS_IMPERIAL:
        return pounds
    return "%s (%s)" % (pounds, kilo)


def thread_diameter_inline(thread: Thread, units: str) -> str:
    """A thread diameter in the units the caller asked for, kept to one system."""
    if units == UNITS_IMPERIAL:
        return fmt_inches(thread.diameter_mm)
    return fmt_mm(thread.diameter_mm)


def thread_diameter_text(thread: Thread, units: str) -> str:
    if units == UNITS_IMPERIAL:
        return fmt_inches(thread.diameter_mm)
    if units == UNITS_BOTH:
        return "%s (%s)" % (fmt_mm(thread.diameter_mm), fmt_inches(thread.diameter_mm))
    return fmt_mm(thread.diameter_mm)


@dataclass(frozen=True)
class NeedleReport:
    thread: Thread
    leather: Leather
    units: str
    primary: Needle
    alternate: Optional[Needle]
    assumptions: Tuple[str, ...]

    @property
    def title(self) -> str:
        return "BeeswaxBind: needle and thread recommender"

    def rationale(self) -> str:
        return "thread %s (%s) takes %s; the eye clears the thread without opening the seam on %s leather" % (
            self.thread.number,
            thread_diameter_inline(self.thread, self.units),
            needle_size_text(self.primary, self.units),
            self.leather.describe(self.units),
        )

    def assumption_lines(self) -> List[str]:
        return list(self.assumptions) if self.assumptions else ["none - every value came from the flags"]

    def thread_line(self) -> str:
        return "%s (%s ply, %s, %s break)" % (
            self.thread.number,
            self.thread.ply_count,
            thread_diameter_text(self.thread, self.units),
            breaking_strength_text(self.thread, self.units),
        )

    def to_text(self) -> str:
        units = self.units
        rows = [["primary", needle_size_text(self.primary, units)]]
        if self.alternate is not None:
            rows.append(["alternate", needle_size_text(self.alternate, units)])
        lengths = [self.primary.length_mm] + ([self.alternate.length_mm] if self.alternate else [])
        length_text = " / ".join(fmt_measure(length, units) for length in lengths)
        blocks = [
            _heading(self.title),
            _section("inputs", [
                _line("thread", self.thread_line()),
                _line("leather", self.leather.describe(units)),
                _line("units", units),
            ]),
            _section("recommendation", [_line(row[0], row[1]) for row in rows] + [
                _line("needle length", length_text),
            ]),
            _section("rationale", [_line("why", self.rationale())]),
            _section("assumptions", [_line("assumed", line) for line in self.assumption_lines()]),
        ]
        return "\n\n".join(blocks)

    def to_json(self) -> dict:
        def needle_obj(needle: Optional[Needle]) -> Optional[dict]:
            if needle is None:
                return None
            return {
                "name": needle.name,
                "metric_mm": needle.metric_mm,
                "us_size": needle.us_size,
                "length_mm": needle.length_mm,
            }

        return {
            "command": "needle",
            "inputs": {
                "thread": self.thread.number,
                "leather_oz": round(self.leather.oz, 3),
                "leather_mm": round(self.leather.mm, 3),
                "units": self.units,
            },
            "needle": needle_obj(self.primary),
            "alternate": needle_obj(self.alternate),
            "rationale": self.rationale(),
            "assumptions": self.assumption_lines(),
        }


def build_needle_report(thread: Thread, leather: Leather, units: str, assumptions: Sequence[str]) -> NeedleReport:
    primary, alternate = pick_needles(thread, leather.oz)
    return NeedleReport(
        thread=thread,
        leather=leather,
        units=units,
        primary=primary,
        alternate=alternate,
        assumptions=tuple(assumptions),
    )


# ---------------------------------------------------------------------------
# Stitch tension calculator (F2)
# ---------------------------------------------------------------------------


def spi_to_length_mm(spi: float) -> float:
    return MM_PER_INCH / spi


def length_mm_to_spi(length_mm: float) -> float:
    return MM_PER_INCH / length_mm


def band_for_leather(leather_oz: float) -> TensionBand:
    for band in TENSION_BANDS:
        if band.low_oz <= leather_oz < band.high_oz:
            return band
    if leather_oz >= TENSION_BANDS[-1].high_oz:
        return TENSION_BANDS[-1]
    return TENSION_BANDS[0]


@dataclass(frozen=True)
class TensionReport:
    spi: float
    length_mm: float
    thread: Thread
    needle: Needle
    leather: Leather
    units: str
    verdict: str
    assumptions: Tuple[str, ...]

    @property
    def title(self) -> str:
        return "BeeswaxBind: stitch tension calculator"

    @property
    def length_in(self) -> float:
        return self.length_mm / MM_PER_INCH

    def reason(self) -> str:
        band = band_for_leather(self.leather.oz)
        needle = needle_size_text(self.needle, self.units)
        span = "%g-%g spi" % (band.min_spi, band.max_spi)
        if self.verdict == "tight":
            return "%s is above the %s band; thread %s on %s leather is pulled harder than %s is comfortable with" % (
                "%.2f spi" % self.spi, span, self.thread.number, self.leather.describe(self.units), needle,
            )
        if self.verdict == "loose":
            return "%s is below the %s band; thread %s on %s leather will sit slack against %s" % (
                "%.2f spi" % self.spi, span, self.thread.number, self.leather.describe(self.units), needle,
            )
        return "%s sits inside the %s band for thread %s and %s on %s leather" % (
            "%.2f spi" % self.spi, span, self.thread.number, needle, self.leather.describe(self.units),
        )

    def assumption_lines(self) -> List[str]:
        return list(self.assumptions) if self.assumptions else ["none - every value came from the flags"]

    def to_text(self) -> str:
        units = self.units
        thread_line = "%s (%s ply, %s, %s break)" % (
            self.thread.number,
            self.thread.ply_count,
            thread_diameter_text(self.thread, units),
            breaking_strength_text(self.thread, units),
        )
        blocks = [
            _heading(self.title),
            _section("inputs", [
                _line("stitch density", "%.2f spi" % self.spi),
                _line("stitch length", fmt_measure(self.length_mm, units)),
                _line("thread", thread_line),
                _line("leather", self.leather.describe(units)),
                _line("needle", needle_size_text(self.needle, units)),
                _line("units", units),
            ]),
            _section("tension verdict", [
                _line("verdict", self.verdict),
                _line("reason", self.reason()),
            ]),
            _section("assumptions", [_line("assumed", line) for line in self.assumption_lines()]),
        ]
        return "\n\n".join(blocks)

    def to_json(self) -> dict:
        return {
            "command": "tension",
            "inputs": {
                "spi": round(self.spi, 4),
                "thread": self.thread.number,
                "leather_oz": round(self.leather.oz, 3),
                "leather_mm": round(self.leather.mm, 3),
                "units": self.units,
            },
            "result": {
                "spi": round(self.spi, 2),
                "stitch_length_mm": round(self.length_mm, 2),
                "stitch_length_in": round(self.length_in, 2),
                "thread_number": self.thread.number,
                "needle_metric_mm": self.needle.metric_mm,
                "verdict": self.verdict,
                "reason": self.reason(),
            },
            "assumptions": self.assumption_lines(),
        }


def build_tension_report(
    spi: float,
    thread: Thread,
    leather: Leather,
    units: str,
    assumptions: Sequence[str],
) -> TensionReport:
    length_mm = spi_to_length_mm(spi)
    band = band_for_leather(leather.oz)
    if spi > band.max_spi:
        verdict = "tight"
    elif spi < band.min_spi:
        verdict = "loose"
    else:
        verdict = "standard"
    needle, _alternate = pick_needles(thread, leather.oz)
    return TensionReport(
        spi=spi,
        length_mm=length_mm,
        thread=thread,
        needle=needle,
        leather=leather,
        units=units,
        verdict=verdict,
        assumptions=tuple(assumptions),
    )


# ---------------------------------------------------------------------------
# Wax blend ratio helper (F3)
# ---------------------------------------------------------------------------


def recipe_for_parts(beeswax: Fraction, rosin: Fraction) -> Optional[WaxRecipe]:
    for recipe in WAX_RECIPES:
        if recipe.beeswax_parts == beeswax and recipe.rosin_parts == rosin:
            return recipe
    return None


@dataclass(frozen=True)
class WaxReport:
    beeswax_parts: Fraction
    rosin_parts: Fraction
    batch_grams: float
    units: str
    recipe: Optional[WaxRecipe]
    assumptions: Tuple[str, ...]

    @property
    def title(self) -> str:
        return "BeeswaxBind: thread-wax blend"

    @property
    def ratio_label(self) -> str:
        return "%s:%s" % (_frac_text(self.beeswax_parts), _frac_text(self.rosin_parts))

    @property
    def total_parts(self) -> Fraction:
        return self.beeswax_parts + self.rosin_parts

    @property
    def beeswax_grams(self) -> float:
        return float(Fraction(self.batch_grams) * self.beeswax_parts / self.total_parts)

    @property
    def rosin_grams(self) -> float:
        return float(Fraction(self.batch_grams) * self.rosin_parts / self.total_parts)

    @property
    def beeswax_pct(self) -> int:
        return int(round(100.0 * float(self.beeswax_parts / self.total_parts)))

    @property
    def rosin_pct(self) -> int:
        return 100 - self.beeswax_pct

    def assumption_lines(self) -> List[str]:
        lines = list(self.assumptions)
        if self.recipe is not None and not self.assumptions:
            lines.append("blend matches the bundled %s recipe" % self.recipe.preset)
        return lines if lines else ["none - every value came from the flags"]

    def to_text(self) -> str:
        units = self.units
        rows = [
            ["beeswax", fmt_weight(self.beeswax_grams, units), "%d%%" % self.beeswax_pct],
            ["rosin", fmt_weight(self.rosin_grams, units), "%d%%" % self.rosin_pct],
            ["total", fmt_weight(self.batch_grams, units), "100%"],
        ]
        table = render_table(["component", "weight", "share"], rows)
        table = "\n".join("  " + line for line in table.splitlines())
        blocks = [
            _heading(self.title),
            _section("inputs", [
                _line("ratio", "%s beeswax:rosin" % self.ratio_label),
                _line("batch", fmt_weight(self.batch_grams, units)),
                _line("units", units),
            ]),
            _section("blend", [table]),
            _section("assumptions", [_line("assumed", line) for line in self.assumption_lines()]),
        ]
        if self.recipe is not None:
            blocks.insert(-1, _section("note", [_line("use", self.recipe.use_note)]))
        return "\n\n".join(blocks)

    def to_json(self) -> dict:
        return {
            "command": "wax",
            "ratio": self.ratio_label,
            "preset": self.recipe.preset if self.recipe else None,
            "batch_grams": round(self.batch_grams, 2),
            "batch_oz": round(self.batch_grams / GRAMS_PER_OZ, 3),
            "beeswax_grams": round(self.beeswax_grams, 1),
            "beeswax_oz": round(self.beeswax_grams / GRAMS_PER_OZ, 2),
            "rosin_grams": round(self.rosin_grams, 1),
            "rosin_oz": round(self.rosin_grams / GRAMS_PER_OZ, 2),
            "beeswax_pct": self.beeswax_pct,
            "rosin_pct": self.rosin_pct,
            "units": self.units,
            "assumptions": self.assumption_lines(),
        }


def build_wax_report(
    beeswax_parts: Fraction,
    rosin_parts: Fraction,
    batch_grams: float,
    units: str,
    assumptions: Sequence[str],
    recipe: Optional[WaxRecipe] = None,
) -> WaxReport:
    return WaxReport(
        beeswax_parts=beeswax_parts,
        rosin_parts=rosin_parts,
        batch_grams=batch_grams,
        units=units,
        recipe=recipe if recipe is not None else recipe_for_parts(beeswax_parts, rosin_parts),
        assumptions=tuple(assumptions),
    )

# ---------------------------------------------------------------------------
# Bundled reference tables and search (F5)
# ---------------------------------------------------------------------------


def _thread_diameter_cell(thread: Thread, units: str) -> str:
    return fmt_inches(thread.diameter_mm) if units == UNITS_IMPERIAL else fmt_mm(thread.diameter_mm)


def _breaking_cell(thread: Thread, units: str) -> str:
    if units == UNITS_METRIC:
        return "%g kg" % thread.breaking_kg
    if units == UNITS_IMPERIAL:
        return "%g lb" % thread.breaking_lb
    return "%g lb (%g kg)" % (thread.breaking_lb, thread.breaking_kg)


def threads_table(threads: Sequence[Thread], units: str) -> str:
    rows = [
        [t.number, str(t.ply_count), _thread_diameter_cell(t, units), _breaking_cell(t, units), t.note]
        for t in threads
    ]
    return render_table(["number", "ply", "diameter", "breaking", "notes"], rows)


def needles_table(needles: Sequence[Needle], units: str) -> str:
    headers = ["size"]
    if units != UNITS_IMPERIAL:
        headers.append("metric mm")
    if units != UNITS_METRIC:
        headers.append("US size")
    headers += ["length", "fits threads"]
    rows = []
    for needle in needles:
        row = [needle.name]
        if units != UNITS_IMPERIAL:
            row.append(fmt_size(needle.metric_mm))
        if units != UNITS_METRIC:
            row.append(needle.us_size)
        row.append(fmt_measure(needle.length_mm, units))
        row.append(", ".join(needle.fits_threads))
        rows.append(row)
    return render_table(headers, rows)


def _wax_rows(recipes: Sequence[WaxRecipe]) -> List[List[str]]:
    rows = []
    for recipe in recipes:
        total = recipe.beeswax_parts + recipe.rosin_parts
        beeswax_pct = int(round(100.0 * float(recipe.beeswax_parts / total)))
        rows.append([
            recipe.preset,
            recipe.ratio_label,
            "%d%%" % beeswax_pct,
            "%d%%" % (100 - beeswax_pct),
            recipe.use_note,
        ])
    return rows


def wax_table(recipes: Sequence[WaxRecipe]) -> str:
    return render_table(["preset", "ratio", "beeswax", "rosin", "use"], _wax_rows(recipes))


def _table_body(name: str, units: str) -> str:
    if name == "threads":
        return threads_table(THREADS, units)
    if name == "needles":
        return needles_table(NEEDLES, units)
    return wax_table(WAX_RECIPES)


def _reference_block(name: str, units: str) -> str:
    return "%s\n%s" % (name, _table_body(name, units))


@dataclass(frozen=True)
class ReferenceReport:
    units: str
    show: Optional[str]
    search: Optional[str]
    body: str
    matched: Tuple[str, ...]

    @property
    def title(self) -> str:
        return "BeeswaxBind: bundled reference tables"

    def to_text(self) -> str:
        first = self.title
        if self.search is not None:
            first = "%s -- search: %s" % (first, self.search)
        return "%s\n%s\n\n%s" % (first, "-" * max(len(first), 16), self.body)

    def to_json(self) -> dict:
        return {
            "command": "reference",
            "show": self.show,
            "search": self.search,
            "units": self.units,
            "tables": list(self.matched),
            "results": _json_results(self.show, self.search),
        }


def _json_results(show: Optional[str], search: Optional[str]) -> dict:
    """Machine-readable rows for the requested tables, with the search applied."""
    results = {}
    for name in TABLE_NAMES:
        if show is not None and show != name:
            continue
        rows = _rows_for_json(name)
        if search is not None:
            rows = [row for row in rows if search.lower() in json.dumps(row).lower()]
        results[name] = rows
    return results


def _rows_for_json(name: str) -> List[dict]:
    if name == "threads":
        return [
            {
                "number": t.number,
                "ply": t.ply_count,
                "diameter_mm": t.diameter_mm,
                "breaking_lb": t.breaking_lb,
                "breaking_kg": t.breaking_kg,
                "notes": t.note,
            }
            for t in THREADS
        ]
    if name == "needles":
        return [
            {
                "name": n.name,
                "metric_mm": n.metric_mm,
                "us_size": n.us_size,
                "length_mm": n.length_mm,
                "fits_threads": list(n.fits_threads),
            }
            for n in NEEDLES
        ]
    return [
        {
            "preset": r.preset,
            "beeswax_parts": _frac_text(r.beeswax_parts),
            "rosin_parts": _frac_text(r.rosin_parts),
            "ratio": r.ratio_label,
            "use": r.use_note,
        }
        for r in WAX_RECIPES
    ]


def _matching_threads(term: str) -> List[Thread]:
    """Match on the thread's own identity: number, diameter or note."""
    needle = term.lower()
    return [
        t for t in THREADS
        if needle in t.number.lower() or needle in t.note.lower() or needle in ("%g" % t.diameter_mm)
    ]


def _matching_needles(term: str) -> List[Needle]:
    """Match on the needle's own identity; threads that fit it are listed separately."""
    needle = term.lower()
    matched = []
    for candidate in NEEDLES:
        haystack = " ".join([
            candidate.name,
            candidate.us_size,
            fmt_mm(candidate.metric_mm),
            fmt_inches(candidate.length_mm),
        ])
        if needle in haystack.lower():
            matched.append(candidate)
    return matched


def _matching_wax(term: str) -> List[WaxRecipe]:
    needle = term.lower()
    return [r for r in WAX_RECIPES if needle in r.preset.lower() or needle in r.use_note.lower() or needle in r.ratio_label]


def build_reference_report(units: str, show: Optional[str], search: Optional[str]) -> ReferenceReport:
    if show is not None:
        show = parse_table_name(show)
    if search is None:
        names = (show,) if show is not None else TABLE_NAMES
        body = "\n\n".join(_reference_block(name, units) for name in names)
        return ReferenceReport(units=units, show=show, search=None, body=body, matched=tuple(names))

    term = search.strip()
    blocks: List[str] = []
    matched: List[str] = []
    threads = _matching_threads(term)
    needles = _matching_needles(term)
    recipes = _matching_wax(term)
    if show in (None, "threads") and threads:
        blocks.append("threads\n" + threads_table(threads, units))
        matched.append("threads")
    if show in (None, "needles") and needles:
        blocks.append("needles\n" + needles_table(needles, units))
        matched.append("needles")
    if show in (None, "wax") and recipes:
        blocks.append("wax\n" + wax_table(recipes))
        matched.append("wax")

    fitted = sorted(
        {needle.name: needle for thread in threads for needle in needles_for_thread(thread.number)}.values(),
        key=lambda n: -n.metric_mm,
    )
    if not blocks:
        body = "no reference rows match '%s'\nsearchable tables: %s" % (term, ", ".join(TABLE_NAMES))
        matched = []
    else:
        if fitted:
            blocks.append("needles that fit the matched threads\n" + needles_table(fitted, units))
        body = "\n\n".join(blocks)
    return ReferenceReport(units=units, show=show, search=term, body=body, matched=tuple(matched))

# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------

COMMANDS = ("needle", "tension", "wax", "reference")

NEEDLE_USAGE = "needle needs --thread; for example: beeswaxbind needle --thread 18/3 --leather 4oz"
TENSION_USAGE = "tension needs --spi or --length; for example: beeswaxbind tension --spi 6"
WAX_USAGE = "wax needs --parts or --preset; for example: beeswaxbind wax --parts 5:1 --batch 100g"

EPILOG = """examples:
  beeswaxbind needle --thread 18/3 --leather 4oz
  beeswaxbind needle --thread 25/3 --leather 2mm --units metric
  beeswaxbind tension --spi 6
  beeswaxbind tension --length 4mm --thread 18/3 --leather 8oz
  beeswaxbind wax --parts 5:1 --batch 100g
  beeswaxbind wax --preset hard --batch 2oz
  beeswaxbind reference --show threads
  beeswaxbind reference --search 18/3
  beeswaxbind needle --thread 18/3 --json

--units metric|imperial|both (default both) controls which size columns appear.
Run with no command on a terminal for the prompt-and-answer wizard.
"""


class _Exit(Exception):
    """Raised by argparse for --help and --version so the caller owns the exit code."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise ValidationError("arguments", message)

    def exit(self, status: int = 0, message: Optional[str] = None) -> None:  # type: ignore[override]
        if message:
            sys.stderr.write(message)
        raise _Exit(status)


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--units", default=UNITS_BOTH, metavar="metric|imperial|both", help="size columns to print (default: both)")
    parser.add_argument("--json", action="store_true", help="emit a single JSON object instead of aligned text")
    parser.add_argument("--color", "--colour", dest="color", default="auto", choices=COLOUR_CHOICES, metavar="auto|always|never", help="accent colour: auto (default) colours a terminal only, so pipes stay plain")


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog=PROG,
        description="BeeswaxBind: harness needle, thread size and thread-wax reference for leathercraft.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="%s %s" % (PROG, __version__))
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", title="commands")

    needle = subparsers.add_parser(
        "needle",
        help="recommend harness needle sizes for a thread number and leather weight",
        description="BeeswaxBind: recommend harness needle sizes for a linen thread number and a leather weight.",
        epilog="examples:\n  beeswaxbind needle --thread 18/3 --leather 4oz\n  beeswaxbind needle --thread 18/3 --leather 2mm --units metric\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    needle.add_argument("--thread", metavar="NUMBER", help="linen thread number such as 18/3")
    needle.add_argument("--leather", metavar="WEIGHT", help="leather weight such as 4oz or 2mm (default: 4oz)")
    _add_common_flags(needle)

    tension = subparsers.add_parser(
        "tension",
        help="convert stitch density and stitch length, and judge the tension",
        description="BeeswaxBind: convert between stitches per inch and stitch length, then judge the tension.",
        epilog="examples:\n  beeswaxbind tension --spi 6\n  beeswaxbind tension --length 4mm --thread 18/3 --leather 8oz\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    tension.add_argument("--spi", metavar="N", help="stitches per inch such as 6")
    tension.add_argument("--length", metavar="LENGTH", help="stitch length such as 4mm or 0.17in")
    tension.add_argument("--thread", metavar="NUMBER", help="linen thread number (default: 18/3)")
    tension.add_argument("--leather", metavar="WEIGHT", help="leather weight such as 4oz or 2mm (default: 4oz)")
    _add_common_flags(tension)

    wax = subparsers.add_parser(
        "wax",
        help="scale a beeswax:rosin blend to a batch weight",
        description="BeeswaxBind: scale a beeswax:rosin thread-wax blend to a batch weight (canonical presets: %s)." % ", ".join(CANONICAL_PRESETS),
        epilog="examples:\n  beeswaxbind wax --parts 5:1 --batch 100g\n  beeswaxbind wax --preset hard --batch 2oz\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    wax.add_argument("--parts", metavar="BEESWAX:ROSIN", help="parts ratio such as 5:1")
    wax.add_argument("--batch", metavar="WEIGHT", help="batch weight such as 100g or 2oz (default: 50g)")
    wax.add_argument("--preset", metavar="NAME", help="named recipe: %s" % ", ".join(PRESET_BY_NAME))
    _add_common_flags(wax)

    reference = subparsers.add_parser(
        "reference",
        help="browse or search the bundled thread, needle and wax tables",
        description="BeeswaxBind: browse and search the bundled thread, needle and wax tables.",
        epilog="examples:\n  beeswaxbind reference --show threads\n  beeswaxbind reference --search 18/3\n  beeswaxbind reference --show needles --units imperial\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    reference.add_argument("--show", metavar="TABLE", help="one table: %s" % ", ".join(TABLE_NAMES))
    reference.add_argument("--search", metavar="TEXT", help="filter every table by a word or size")
    _add_common_flags(reference)

    return parser


def _first_positional(argv: Sequence[str]) -> Optional[str]:
    for token in argv:
        if token == "--":
            return None
        if not token.startswith("-"):
            return token
    return None


def _emit_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def _emit_report(report, json_mode: bool) -> int:
    if json_mode:
        _emit_json(report.to_json())
    else:
        sys.stdout.write(_render_text(report) + "\n")
    return EXIT_OK

# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _default_leather() -> Leather:
    return Leather(DEFAULT_LEATHER_OZ, DEFAULT_LEATHER_OZ * MM_PER_OZ, "oz", DEFAULT_LEATHER_OZ)


def command_needle(args: argparse.Namespace) -> int:
    units = parse_units(args.units)
    leather = parse_leather(args.leather) if args.leather is not None else None
    if args.thread is None:
        if leather is None:
            return _fallback_to_wizard("needle", units, args.json, NEEDLE_USAGE)
        raise ValidationError("thread", NEEDLE_USAGE)
    thread = parse_thread_number(args.thread)
    assumptions: List[str] = []
    if leather is None:
        leather = _default_leather()
        assumptions.append("%s leather assumed (default)" % fmt_oz(leather.oz))
    report = build_needle_report(thread, leather, units, assumptions)
    return _emit_report(report, args.json)


def _tension_assumptions(thread_defaulted: bool, leather_defaulted: bool, thread: Thread, leather: Leather) -> List[str]:
    if thread_defaulted and leather_defaulted:
        return ["thread %s and %s leather assumed (defaults)" % (thread.number, fmt_oz(leather.oz))]
    if thread_defaulted:
        return ["thread %s assumed (default)" % thread.number]
    if leather_defaulted:
        return ["%s leather assumed (default)" % fmt_oz(leather.oz)]
    return []


def command_tension(args: argparse.Namespace) -> int:
    units = parse_units(args.units)
    if args.spi is not None and args.length is not None:
        raise ValidationError("spi", "give either --spi or --length, not both; for example: beeswaxbind tension --spi 6")
    if args.spi is not None:
        spi = parse_spi(args.spi)
    elif args.length is not None:
        spi = length_mm_to_spi(parse_length(args.length))
    else:
        if args.thread is None and args.leather is None:
            return _fallback_to_wizard("tension", units, args.json, TENSION_USAGE)
        raise ValidationError("spi", TENSION_USAGE)

    thread_defaulted = args.thread is None
    leather_defaulted = args.leather is None
    thread = parse_thread_number(args.thread) if not thread_defaulted else parse_thread_number(DEFAULT_THREAD)
    leather = parse_leather(args.leather) if not leather_defaulted else _default_leather()
    assumptions = _tension_assumptions(thread_defaulted, leather_defaulted, thread, leather)
    report = build_tension_report(spi, thread, leather, units, assumptions)
    return _emit_report(report, args.json)


def command_wax(args: argparse.Namespace) -> int:
    units = parse_units(args.units)
    if args.batch is not None:
        batch_grams = parse_batch_grams(args.batch)
        batch_assumptions: List[str] = []
    else:
        batch_grams = DEFAULT_BATCH_GRAMS
        batch_assumptions = ["%s batch assumed (default)" % fmt_g(DEFAULT_BATCH_GRAMS)]

    if args.parts is not None and args.preset is not None:
        raise ValidationError("parts", "give either --parts or --preset, not both; for example: beeswaxbind wax --parts 5:1")
    recipe = None
    if args.preset is not None:
        recipe = parse_preset(args.preset)
        beeswax_parts, rosin_parts = recipe.beeswax_parts, recipe.rosin_parts
    elif args.parts is not None:
        beeswax_parts, rosin_parts = parse_parts(args.parts)
    else:
        if args.batch is None:
            return _fallback_to_wizard("wax", units, args.json, WAX_USAGE)
        raise ValidationError("parts", WAX_USAGE)

    report = build_wax_report(beeswax_parts, rosin_parts, batch_grams, units, batch_assumptions, recipe)
    return _emit_report(report, args.json)


def command_reference(args: argparse.Namespace) -> int:
    units = parse_units(args.units)
    report = build_reference_report(units, args.show, args.search)
    return _emit_report(report, args.json)


COMMAND_HANDLERS = {
    "needle": command_needle,
    "tension": command_tension,
    "wax": command_wax,
    "reference": command_reference,
}


def report_error(error: ValidationError, json_mode: bool) -> int:
    """One readable stderr line (or one JSON object) and exit code 2."""
    if json_mode:
        sys.stderr.write(json.dumps({"error": error.message, "field": error.field}) + "\n")
    else:
        sys.stderr.write("%s: error: %s\n" % (PROG, error.message))
        sys.stderr.write("hint: run '%s --help' for usage and examples\n" % PROG)
    return error.exit_code

# ---------------------------------------------------------------------------
# Interactive wizard (F4)
# ---------------------------------------------------------------------------

WIZARD_MENU = """BeeswaxBind interactive - pick a calculator
  1  needle     recommend harness needle sizes for a thread and leather weight
  2  tension    convert stitch density and stitch length, and judge the tension
  3  wax        scale a beeswax:rosin blend to a batch weight
"""

NO_COMMAND_HELP = """BeeswaxBind needs a command when it is not running on a terminal.
  needle      recommend harness needle sizes for a thread and leather weight
  tension     convert stitch density and stitch length, and judge the tension
  wax         scale a beeswax:rosin blend to a batch weight
  reference   browse and search the bundled tables
hint: run 'beeswaxbind --help' for usage and examples, or run beeswaxbind on a
      terminal for the prompt-and-answer wizard
"""


class _WizardEOF(Exception):
    """Raised when the answer stream ends; the carried code is the exit code."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class _LineReader:
    """Reads answers from a terminal or from piped lines, echoing them either way."""

    def __init__(self, lines: Optional[Iterable[str]] = None, stream=None) -> None:
        self._lines = None if lines is None else iter(lines)
        self._stream = stream if stream is not None else sys.stdout

    def read(self, prompt: str) -> Optional[str]:
        self._stream.write(prompt)
        self._stream.flush()
        if self._lines is None:
            try:
                return input()
            except EOFError:
                self._stream.write("\n")
                return None
        try:
            line = next(self._lines)
        except StopIteration:
            self._stream.write("\n")
            return None
        self._stream.write(line + "\n")
        return line

    def note(self, text: str) -> None:
        self._stream.write("  ! %s\n" % text)


def _stdin_reader() -> Optional[_LineReader]:
    """A reader for the wizard, or None when there is no input to drive it."""
    stream = sys.stdin
    if stream is None:  # stdin was closed outright, e.g. `beeswaxbind 0<&-`
        return None
    try:
        interactive = stream.isatty()
    except (AttributeError, ValueError):
        interactive = False
    if interactive:
        return _LineReader()
    try:
        data = stream.read()
    except (OSError, ValueError):
        return None
    if not data.strip():
        return None
    return _LineReader(data.splitlines())


def _report_no_command() -> int:
    sys.stdout.write(NO_COMMAND_HELP)
    return EXIT_USAGE


def _fallback_to_wizard(command: str, units: str, json_mode: bool, message: str) -> int:
    """A calculator with no inputs either asks questions or explains what to pass."""
    if json_mode:
        raise ValidationError("arguments", message)
    reader = _stdin_reader()
    if reader is None:
        raise ValidationError("arguments", message)
    return _run_wizard(command=command, units=units, reader=reader)


def _ask(reader: _LineReader, prompt: str, default: Optional[str], parser) -> Tuple[object, bool]:
    """One question, re-asked with a short reason until the answer parses."""
    while True:
        line = reader.read(prompt)
        if line is None:
            raise _WizardEOF(EXIT_OK)
        text = line.strip()
        used_default = False
        if not text:
            if default is None:
                reader.note("a value is required here")
                continue
            text = default
            used_default = True
        try:
            return parser(text), used_default
        except ValidationError as error:
            reader.note(error.message)


def _parse_density(text: str) -> float:
    """Accept either a stitch density (6) or a stitch length (4mm) as the answer."""
    cleaned = text.strip().lower()
    if cleaned.endswith(("mm", "in", '"')):
        return length_mm_to_spi(parse_length(cleaned))
    return parse_spi(cleaned)


def _wizard_calculate(reader: _LineReader, command: str, units: str):
    if command == "needle":
        thread, _ = _ask(reader, "Thread number [18/3]: ", DEFAULT_THREAD, parse_thread_number)
        leather, leather_defaulted = _ask(reader, "Leather weight in oz or mm [4oz]: ", "4oz", parse_leather)
        assumptions = ["%s leather assumed (default)" % fmt_oz(leather.oz)] if leather_defaulted else []
        return build_needle_report(thread, leather, units, assumptions)

    if command == "tension":
        spi, _ = _ask(
            reader,
            "Stitches per inch or a stitch length such as 4mm [%g]: " % DEFAULT_SPI,
            "%g" % DEFAULT_SPI,
            _parse_density,
        )
        thread, thread_defaulted = _ask(reader, "Thread number [18/3]: ", DEFAULT_THREAD, parse_thread_number)
        leather, leather_defaulted = _ask(reader, "Leather weight in oz or mm [4oz]: ", "4oz", parse_leather)
        return build_tension_report(
            spi, thread, leather, units,
            _tension_assumptions(thread_defaulted, leather_defaulted, thread, leather),
        )

    beeswax_parts, rosin_parts = _ask(reader, "Beeswax:rosin parts [5:1]: ", DEFAULT_PARTS, parse_parts)[0]
    batch_grams, batch_defaulted = _ask(reader, "Batch weight such as 100g or 2oz [50g]: ", "50g", parse_batch_grams)
    assumptions = ["%s batch assumed (default)" % fmt_g(DEFAULT_BATCH_GRAMS)] if batch_defaulted else []
    return build_wax_report(beeswax_parts, rosin_parts, batch_grams, units, assumptions)


def _wizard_menu(reader: _LineReader) -> str:
    sys.stdout.write("\n" + WIZARD_MENU)
    while True:
        line = reader.read("Choose a calculator [1-3, q to quit] (default 1): ")
        if line is None:
            raise _WizardEOF(EXIT_USAGE)
        text = line.strip().lower()
        if text.startswith("q"):
            raise _WizardEOF(EXIT_OK)
        if text in ("", "1", "needle"):
            return "needle"
        if text in ("2", "tension"):
            return "tension"
        if text in ("3", "wax"):
            return "wax"
        reader.note("enter 1 for needle, 2 for tension, 3 for wax, or q to quit")


def _run_wizard(command: Optional[str] = None, units: str = UNITS_BOTH, reader: Optional[_LineReader] = None) -> int:
    """The prompt-and-answer fallback: same reports as the flag-driven commands."""
    if reader is None:
        reader = _stdin_reader()
        if reader is None:
            return _report_no_command()
    produced = False
    try:
        while True:
            choice = _wizard_menu(reader) if command is None else command
            report = _wizard_calculate(reader, choice, units)
            sys.stdout.write("\n" + _render_text(report) + "\n\n")
            produced = True
            again = reader.read("press Enter to run another calculation, q to quit: ")
            if again is None or again.strip().lower().startswith("q"):
                return EXIT_OK
            command = None
    except _WizardEOF as stop:
        if stop.code == EXIT_USAGE and not produced:
            return _report_no_command()
        return EXIT_OK


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    if sys.stdout is None:  # stdout was closed outright, e.g. `beeswaxbind ... 1>&-`
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in arguments
    try:
        parser = build_parser()
        first = _first_positional(arguments)
        if first is not None and first not in COMMANDS:
            raise ValidationError("command", "unknown command: %s; run '%s --help' for the command list" % (first, PROG))
        args = parser.parse_args(arguments)
        _set_colour(getattr(args, "color", "auto"))
        if args.command is None:
            return _run_wizard()
        return COMMAND_HANDLERS[args.command](args)
    except ValidationError as error:
        return report_error(error, json_mode)
    except _Exit as stop:
        return stop.code
    except KeyboardInterrupt:
        sys.stderr.write("\ninterrupted\n")
        return 130
    except BrokenPipeError:
        return EXIT_OK


if __name__ == "__main__":
    status = main()
    try:
        sys.stdout.flush()
    except BrokenPipeError:
        # the reader closed the pipe early (for example `beeswaxbind ... | head`)
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        status = EXIT_OK
    sys.exit(status)
