from __future__ import annotations

# Ordering analysis for a Fanzine Index Page.
#
# A FIP's issues should be listed in a sorted order, but the data the sort is based on is fragmentary.
# There are several independent ordering *signals*, each of which may be present, partly present, or absent on any row:
#       Date    -- the Year / Month / Day columns (year-only, month+year, or a full date)
#       Whole   -- the Whole (absolute sequence) number; may be messy (102A, XIV, 12.5, ...)
#       Vol+Num -- a Volume (major) + Number (minor) pair; Num restarts within each Vol
#       Serial  -- a number parsed out of the filename in the Link column (e.g. Warhoon28.pdf -> 28)
#
# The list should be in ASCENDING order by every signal that is present.  We produce two kinds of verdict:
#
#   YELLOW (out of order) -- wherever a signal *descends* down the displayed list, the list isn't ascending
#                            there.  This is an ordering problem, not bad data: a row is in the wrong place,
#                            or one of its values is wrong.  We color the complement of the longest
#                            already-ascending subsequence (a heuristic, not provably minimal), which localizes
#                            the problem to the offending row(s), and we name which of the row's signals are out
#                            of line.  Cross-signal disagreement (the date runs one way, the whole number
#                            another) is just this: one row is out of place, flagged yellow -- NOT a pink
#                            contradiction.
#   PINK (invalid value)  -- a cell that has content but cannot be parsed (e.g. a non-number in a number
#                            column).  Bad months/years/days are pinked by the grid's own type coloring, not here.
#
# A row that is internally fine but out of order gets yellow; a cell with genuinely invalid data gets pink.
# (Whole and Vol+Num are kept as independent signals; "Whole trumps Vol+Num" only matters to the future sort.
# The filename serial is the lowest-priority tiebreaker for the future sort.)

import re

from FanzineDateTime import MonthNameToInt
from HelpersPackage import ExtractTrailingSequenceNumber


# Pairwise comparison results
_LESS = -1      # a sorts before b
_GREATER = 1    # a sorts after b
_TIE = 0        # equal as far as comparable -- imposes no constraint
_NA = None      # incomparable: the signal is absent (or insufficient) on at least one side


def _cmp(x, y) -> int:
    if x < y:
        return _LESS
    if x > y:
        return _GREATER
    return _TIE


# Human-readable names for the ordering signals, used in tooltip messages
_SIGNAL_LABELS = {"date": "date", "whole": "whole number", "volnum": "volume/number", "serial": "filename number"}


def _LabelList(names, conj: str="and") -> str:
    labels = [_SIGNAL_LABELS.get(n, n) for n in sorted(names)]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return labels[0] + " " + conj + " " + labels[1]
    return ", ".join(labels[:-1]) + ", " + conj + " " + labels[-1]


# ---- Messy-number parsing (Whole, Vol, Num) ---------------------------------------------------------
_ROMAN_RE = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _RomanToInt(s: str) -> int:
    total = 0
    prev = 0
    for ch in reversed(s):
        v = _ROMAN_VALUES[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


# Reduce a messy number to a sortable key (leadingValue, trailingText), or None if the (non-empty) text
# yields no usable leading number.  The proper ordering is by the leading number, with the trailing bit
# (e.g. the "A" in "102A") as a secondary tiebreak.
def ParseMessyNumber(s: str) -> tuple[float, str] | None:
    s = s.strip()
    if s == "":
        return None
    # A leading integer or decimal, optionally followed by trailing junk
    m = re.match(r"(\d+(?:\.\d+)?)(.*)$", s)
    if m is not None:
        return (float(m.group(1)), m.group(2).strip().lower())
    # A leading roman numeral (the whole leading token must be a valid roman numeral)
    m = re.match(r"([IVXLCDM]+)\b(.*)$", s, flags=re.IGNORECASE)
    if m is not None and _ROMAN_RE.match(m.group(1).upper()):
        return (float(_RomanToInt(m.group(1).upper())), m.group(2).strip().lower())
    return None


# Parse a serial number out of a filename in the Link column.  Returns an int or None.
# Filenames are a noisy source -- a trailing number is just as likely to be a date or an editor's
# initial as an issue number (e.g. "apollo_2_hensley_1943-11.pdf" ends in the *month*, not issue 2).
# So we only trust a serial when it is unambiguous: the filename must contain exactly one run of
# digits, no embedded year, and no Vol+Num pattern.  Anything ambiguous yields None (no serial).
def ExtractSerial(filename: str) -> int | None:
    name = filename.strip()
    if name == "":
        return None
    base = re.sub(r"\.[a-zA-Z0-9]{1,5}$", "", name)     # Drop a trailing extension
    if re.search(r"v\s*\d+\s*n\s*\d+", base, flags=re.IGNORECASE):
        return None     # A Vol+Num filename (e.g. Quip_v2n3), not a plain serial
    if re.search(r"(?:19|20)\d{2}", base):
        return None     # Contains a year -> trailing digits are probably a date, not a serial
    runs = re.findall(r"\d+", base)
    if len(runs) == 1:
        return int(runs[0])     # Exactly one number in the name -> trust it (Warhoon28 -> 28)
    return None         # No number, or several (ambiguous which is the issue number)


# ---- The analysis result ----------------------------------------------------------------------------
class OrderingAnalysis:
    def __init__(self) -> None:
        self.PinkCells: set[tuple[int, int]] = set()        # (irow, icol) -- contradiction or unparseable
        self.YellowRows: set[int] = set()                   # irow -- mis-ordered rows
        self.ValidMessyCells: set[tuple[int, int]] = set()  # (irow, icol) -- messy-but-valid Whole/Vol/Num (Option A: not an error)
        self.CellReasons: dict[tuple[int, int], str] = {}   # (irow, icol) -> explanation (for future tooltips)
        self.RowReasons: dict[int, str] = {}                # irow -> explanation (for future tooltips)

    @property
    def IsOK(self) -> bool:
        return len(self.PinkCells) == 0 and len(self.YellowRows) == 0

    def _AddCellReason(self, cell: tuple[int, int], reason: str) -> None:
        if cell in self.CellReasons:
            if reason not in self.CellReasons[cell]:
                self.CellReasons[cell] += "; " + reason
        else:
            self.CellReasons[cell] = reason


def _FindCol(coldefs, names: set[str], preferred: str) -> int:
    for i, cd in enumerate(coldefs):
        if cd.Name in names or getattr(cd, "Preferred", "") == preferred:
            return i
    return -1


def _Cell(row, icol: int) -> str:
    if icol < 0 or icol >= len(row.Cells):
        return ""
    return row.Cells[icol].strip()


# ----------------------------------------------------------------------------------------------------
# Analyze the rows (in display order) and return an OrderingAnalysis.
# rows:    list of FanzineIndexPageTableRow (only normal, non-empty rows participate)
# coldefs: the page's ColDefinitionsList (column index == grid column index; column 0 is the Link/filename)
def AnalyzeOrdering(rows, coldefs) -> OrderingAnalysis:
    result = OrderingAnalysis()

    iYear = _FindCol(coldefs, {"Year"}, "Year")
    iMonth = _FindCol(coldefs, {"Month"}, "Month")
    iDay = _FindCol(coldefs, {"Day"}, "Day")
    iWhole = _FindCol(coldefs, {"Whole", "WholeNum"}, "Whole")
    iVol = _FindCol(coldefs, {"Vol", "Volume"}, "Vol")
    iNum = _FindCol(coldefs, {"Num", "Number"}, "Num")
    iName = _FindCol(coldefs, {"Display Text", "Title"}, "Display Text")   # the issue name, e.g. "Amor 2.5"
    iLink = 0   # Column 0 is always the filename/URL

    normal = [r for r in range(len(rows)) if rows[r].IsNormalRow and not rows[r].IsEmptyRow]
    if len(normal) < 2:
        return result   # Nothing to order

    # ---- Parse each normal row's signal keys (and handle messy/unparseable number cells, Option A) ----
    def ParseYear(row) -> int | None:
        s = _Cell(row, iYear).replace("?", "")
        return int(s) if re.fullmatch(r"\d{1,4}", s) else None     # Unparseable years are pinked by the grid's type coloring

    def ParseMonth(row) -> int | None:
        s = _Cell(row, iMonth)
        return MonthNameToInt(s) if s != "" else None

    def ParseDay(row) -> int | None:
        s = _Cell(row, iDay).replace("?", "")
        if re.fullmatch(r"\d{1,2}", s):
            d = int(s)
            if 1 <= d <= 31:
                return d
        return None

    # Parse a number cell, recording it as messy-but-valid (un-pink) or unparseable (pink)
    def ParseNumberCell(row, icol: int, irow: int) -> tuple[float, str] | None:
        if icol < 0:
            return None
        s = _Cell(row, icol)
        if s == "":
            return None
        key = ParseMessyNumber(s)
        if key is None:
            result.PinkCells.add((irow, icol))
            result._AddCellReason((irow, icol), f'"{s}" cannot be interpreted as a number.')
            return None
        result.ValidMessyCells.add((irow, icol))
        return key

    # The issue number(s) carried in the Display Text name, as a (vol, num) pair of keys. Used as a fallback
    # when the row has no number columns. A name like "Amor 2.5" yields (None, 2.5); a name like
    # "MT Void Vol. 39, No. 45" yields (39, 45). Distinguishing the two matters: a per-volume number restarts
    # at 1 in each new volume, so it must feed the vol+num signal, NOT be mistaken for an absolute (whole)
    # sequence number. Not a number column, so nothing is pinked here.
    def ParseNameNumbers(row) -> tuple:
        if iName < 0:
            return None, None
        s = _Cell(row, iName)
        if s == "":
            return None, None
        # A trailing DATE must not be mistaken for an issue designation -- "Club Notice 8/16/78" would otherwise
        # parse as Vol 16, Num 78 via the nnn/nnn pattern.  Strip m/d/y dates and month/4-digit-year fractions.
        # (A bare nn/nn like "3/4" is left alone: it's genuinely a vol/num.)
        s = re.sub(r"[\s,(\-]*\d{1,2}/\d{1,2}/\d{2,4}\)?\s*$", "", s).strip()
        s = re.sub(r"[\s,(\-]*\d{1,2}/(?:19|20)\d\d\)?\s*$", "", s).strip()
        if s == "":
            return None, None
        _pre, vol, num, _suf = ExtractTrailingSequenceNumber(s)
        numkey = ParseMessyNumber(num) if num.strip() != "" else None
        volkey = ParseMessyNumber(vol) if vol.strip() != "" else None
        return volkey, numkey

    keys: dict[int, dict] = {}
    for r in normal:
        row = rows[r]
        whole = ParseNumberCell(row, iWhole, r)
        vol = ParseNumberCell(row, iVol, r)
        num = ParseNumberCell(row, iNum, r)
        if whole is None and vol is None and num is None:
            # No number columns for this row: fall back to the number(s) in the issue name
            namevol, namenum = ParseNameNumbers(row)
            if namevol is not None:
                vol, num = namevol, namenum     # The name encodes Vol+Num (e.g. "Vol. 39, No. 45")
            else:
                whole = namenum                 # A bare trailing number (e.g. "Amor 2.5", decimals OK)
        # The filename serial is a noisy last resort (e.g. "Amor-025.pdf" -> 25 even though the issue is 2.5),
        # so only fall back to it when the row has no issue number from a column or from its name.
        if whole is not None or vol is not None or num is not None:
            serial = None
        else:
            serial = ExtractSerial(row.Cells[iLink]) if iLink < len(row.Cells) else None
        keys[r] = {"y": ParseYear(row), "mo": ParseMonth(row), "d": ParseDay(row),
                   "whole": whole, "vol": vol, "num": num, "serial": serial}

    # ---- Per-signal pairwise comparisons ----
    def CmpDate(a: int, b: int):
        ka, kb = keys[a], keys[b]
        if ka["y"] is None or kb["y"] is None:      # Year is the anchor: no year on either side -> no date constraint
            return _NA
        if ka["y"] != kb["y"]:
            return _cmp(ka["y"], kb["y"])
        if ka["mo"] is None or kb["mo"] is None:
            return _TIE
        if ka["mo"] != kb["mo"]:
            return _cmp(ka["mo"], kb["mo"])
        if ka["d"] is None or kb["d"] is None:
            return _TIE
        return _cmp(ka["d"], kb["d"])

    def CmpWhole(a: int, b: int):
        ka, kb = keys[a]["whole"], keys[b]["whole"]
        return _NA if ka is None or kb is None else _cmp(ka, kb)

    def CmpVolNum(a: int, b: int):
        va, vb = keys[a]["vol"], keys[b]["vol"]
        na, nb = keys[a]["num"], keys[b]["num"]
        if va is not None and vb is not None:
            if va != vb:
                return _cmp(va, vb)
            return _cmp(na, nb) if na is not None and nb is not None else _TIE
        if va is None and vb is None:
            return _cmp(na, nb) if na is not None and nb is not None else _NA
        return _NA      # One side has a Vol and the other doesn't -> incomparable

    def CmpSerial(a: int, b: int):
        sa, sb = keys[a]["serial"], keys[b]["serial"]
        return _NA if sa is None or sb is None else _cmp(sa, sb)

    # Issue numbering restarts when a zine changes name or series (e.g. "Holmdel ... Vol 4, No 35" is followed
    # by "Lincroft ... Vol 1, No 1"). A number descent onto a No. 1 (or Whole 1) row whose date does not descend
    # is such a restart, not a misordering: split the rows into numbering SEGMENTS there, and only compare the
    # number signals within a segment. (Dates are still compared across the whole page.)
    seg: dict[int, int] = {}
    segid = 0
    lastnumbered = None      # the most recent normal row that carried any number key
    for r in normal:
        k = keys[r]
        hasnum = k["whole"] is not None or k["vol"] is not None or k["num"] is not None
        if hasnum and lastnumbered is not None:
            descends = CmpWhole(lastnumbered, r) == _GREATER or CmpVolNum(lastnumbered, r) == _GREATER
            startish = (k["num"] is not None and k["num"][0] <= 1) or (k["whole"] is not None and k["whole"][0] <= 1)
            if descends and startish and CmpDate(lastnumbered, r) != _GREATER:
                segid += 1
        seg[r] = segid
        if hasnum:
            lastnumbered = r

    # Wrap the number comparisons so rows in different numbering segments are incomparable
    def SegGated(f):
        def g(a: int, b: int):
            if seg[a] != seg[b]:
                return _NA
            return f(a, b)
        return g

    signals = [("date", CmpDate), ("whole", SegGated(CmpWhole)), ("volnum", SegGated(CmpVolNum)), ("serial", CmpSerial)]

    # The list should be in ASCENDING order by every signal (date, whole, vol/num, and the filename serial).
    # Wherever a signal *descends* across a pair of rows, the list isn't ascending there -- that's an ordering
    # problem (yellow), not a data contradiction.  We deliberately do NOT treat two signals disagreeing as an
    # intrinsic "pink" contradiction: when, say, the dates run one way and the whole numbers another, it just
    # means a row is out of place, and the longest-ascending-run heuristic below localizes it to that row.
    # (Pink is reserved for genuinely invalid values -- e.g. an unparseable number, handled above.)

    # ---- Walk every pair: record where a signal descends (an out-of-ascending-order violation) ----
    n = len(normal)
    viol = [[False] * n for _ in range(n)]      # viol[pi][pj] (pi<pj): some signal descends from normal[pi] down to normal[pj]
    descents: dict[tuple[int, int], set] = {}   # (pi,pj) -> the set of signal names that descend across that pair
    for pi in range(n):
        for pj in range(pi + 1, n):
            a, b = normal[pi], normal[pj]       # a is displayed above b
            descending = {signame for signame, func in signals if func(a, b) == _GREATER}
            if descending:
                viol[pi][pj] = True
                descents[(pi, pj)] = descending

    # ---- Color the complement of the longest already-ascending subsequence yellow ----
    # DP for a long valid chain (each chained pair compatible), then a greedy pass to guarantee the kept set is
    # internally valid (the heuristic need not be optimal -- it just has to localize the problem for the user).
    dp = [1] * n
    parent = [-1] * n
    for pj in range(n):
        for pi in range(pj):
            if not viol[pi][pj] and dp[pi] + 1 > dp[pj]:
                dp[pj] = dp[pi] + 1
                parent[pj] = pi
    keepChain: list[int] = []
    k = max(range(n), key=lambda x: dp[x]) if n > 0 else -1
    while k != -1:
        keepChain.append(k)
        k = parent[k]
    keepChain.reverse()

    keep: list[int] = []
    for p in keepChain:
        if all(not viol[q][p] for q in keep):       # q is above p (q<p); p must not be required to sort before q
            keep.append(p)
    keepset = set(keep)

    if len(keepset) < n:
        for p in range(n):
            if p in keepset:
                continue
            result.YellowRows.add(normal[p])
            # Name the signals that put this row out of order relative to the kept (good) rows, for the tooltip.
            badsignals: set = set()
            for q in keepset:
                badsignals |= descents.get((min(p, q), max(p, q)), set())
            if badsignals:
                labels = _LabelList(badsignals, conj="and")
                verb = "is" if len(badsignals) == 1 else "are"
                result.RowReasons[normal[p]] = f"The {labels} of this row {verb} inconsistent with the overall arrangement of the rows (it is out of ascending order)."
            else:
                result.RowReasons[normal[p]] = "This row is out of order -- the list should run in ascending date and number order."

    return result
