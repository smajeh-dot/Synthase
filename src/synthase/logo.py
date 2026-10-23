"""The start-up logo: a woven colour ring drawn in octant characters.

The one module allowed to name colours and use octants (decision 0035). The
maths is the owner-approved design board's, unchanged; tests/test_logo.py pins
its output at 80 × 24 and 120 × 30.
"""

import math

from textual.content import Content

# Colours sampled from the Antigravity 8-bit logo, at degrees clockwise from the top.
STOPS = (
    (0, "#F6912E"),
    (25, "#F37337"),
    (45, "#F0583B"),
    (65, "#E14F59"),
    (85, "#9C5B97"),
    (105, "#8F64B4"),
    (130, "#6C73D8"),
    (155, "#4A81F0"),
    (180, "#3886FB"),
    (205, "#4FA0F8"),
    (225, "#64B6F6"),
    (250, "#6BC7A3"),
    (275, "#61C37D"),
    (295, "#7CC251"),
    (315, "#9EC345"),
    (335, "#DBB131"),
)
THICKNESS_PX = 13
WEAVE = 15
CROSSINGS = 1
TURN = 90
# Windows shorter than this show no logo.
MIN_ROWS = 24

# The character for each octant pattern: OCTANTS[mask], where bit n-1 of mask
# is block n and the blocks are numbered
#   1 2
#   3 4
#   5 6
#   7 8
# Built from Unicode 16.0 and checked against Cascadia Mono 2404.23's outlines.
# Python 3.13's unicodedata is Unicode 15.1 and has no octants.
# fmt: off
OCTANTS = tuple(chr(cp) for cp in (
    0x00020, 0x1CEA8, 0x1CEAB, 0x1FB82, 0x1CD00, 0x02598, 0x1CD01, 0x1CD02,
    0x1CD03, 0x1CD04, 0x0259D, 0x1CD05, 0x1CD06, 0x1CD07, 0x1CD08, 0x02580,
    0x1CD09, 0x1CD0A, 0x1CD0B, 0x1CD0C, 0x1FBE6, 0x1CD0D, 0x1CD0E, 0x1CD0F,
    0x1CD10, 0x1CD11, 0x1CD12, 0x1CD13, 0x1CD14, 0x1CD15, 0x1CD16, 0x1CD17,
    0x1CD18, 0x1CD19, 0x1CD1A, 0x1CD1B, 0x1CD1C, 0x1CD1D, 0x1CD1E, 0x1CD1F,
    0x1FBE7, 0x1CD20, 0x1CD21, 0x1CD22, 0x1CD23, 0x1CD24, 0x1CD25, 0x1CD26,
    0x1CD27, 0x1CD28, 0x1CD29, 0x1CD2A, 0x1CD2B, 0x1CD2C, 0x1CD2D, 0x1CD2E,
    0x1CD2F, 0x1CD30, 0x1CD31, 0x1CD32, 0x1CD33, 0x1CD34, 0x1CD35, 0x1FB85,
    0x1CEA3, 0x1CD36, 0x1CD37, 0x1CD38, 0x1CD39, 0x1CD3A, 0x1CD3B, 0x1CD3C,
    0x1CD3D, 0x1CD3E, 0x1CD3F, 0x1CD40, 0x1CD41, 0x1CD42, 0x1CD43, 0x1CD44,
    0x02596, 0x1CD45, 0x1CD46, 0x1CD47, 0x1CD48, 0x0258C, 0x1CD49, 0x1CD4A,
    0x1CD4B, 0x1CD4C, 0x0259E, 0x1CD4D, 0x1CD4E, 0x1CD4F, 0x1CD50, 0x0259B,
    0x1CD51, 0x1CD52, 0x1CD53, 0x1CD54, 0x1CD55, 0x1CD56, 0x1CD57, 0x1CD58,
    0x1CD59, 0x1CD5A, 0x1CD5B, 0x1CD5C, 0x1CD5D, 0x1CD5E, 0x1CD5F, 0x1CD60,
    0x1CD61, 0x1CD62, 0x1CD63, 0x1CD64, 0x1CD65, 0x1CD66, 0x1CD67, 0x1CD68,
    0x1CD69, 0x1CD6A, 0x1CD6B, 0x1CD6C, 0x1CD6D, 0x1CD6E, 0x1CD6F, 0x1CD70,
    0x1CEA0, 0x1CD71, 0x1CD72, 0x1CD73, 0x1CD74, 0x1CD75, 0x1CD76, 0x1CD77,
    0x1CD78, 0x1CD79, 0x1CD7A, 0x1CD7B, 0x1CD7C, 0x1CD7D, 0x1CD7E, 0x1CD7F,
    0x1CD80, 0x1CD81, 0x1CD82, 0x1CD83, 0x1CD84, 0x1CD85, 0x1CD86, 0x1CD87,
    0x1CD88, 0x1CD89, 0x1CD8A, 0x1CD8B, 0x1CD8C, 0x1CD8D, 0x1CD8E, 0x1CD8F,
    0x02597, 0x1CD90, 0x1CD91, 0x1CD92, 0x1CD93, 0x0259A, 0x1CD94, 0x1CD95,
    0x1CD96, 0x1CD97, 0x02590, 0x1CD98, 0x1CD99, 0x1CD9A, 0x1CD9B, 0x0259C,
    0x1CD9C, 0x1CD9D, 0x1CD9E, 0x1CD9F, 0x1CDA0, 0x1CDA1, 0x1CDA2, 0x1CDA3,
    0x1CDA4, 0x1CDA5, 0x1CDA6, 0x1CDA7, 0x1CDA8, 0x1CDA9, 0x1CDAA, 0x1CDAB,
    0x02582, 0x1CDAC, 0x1CDAD, 0x1CDAE, 0x1CDAF, 0x1CDB0, 0x1CDB1, 0x1CDB2,
    0x1CDB3, 0x1CDB4, 0x1CDB5, 0x1CDB6, 0x1CDB7, 0x1CDB8, 0x1CDB9, 0x1CDBA,
    0x1CDBB, 0x1CDBC, 0x1CDBD, 0x1CDBE, 0x1CDBF, 0x1CDC0, 0x1CDC1, 0x1CDC2,
    0x1CDC3, 0x1CDC4, 0x1CDC5, 0x1CDC6, 0x1CDC7, 0x1CDC8, 0x1CDC9, 0x1CDCA,
    0x1CDCB, 0x1CDCC, 0x1CDCD, 0x1CDCE, 0x1CDCF, 0x1CDD0, 0x1CDD1, 0x1CDD2,
    0x1CDD3, 0x1CDD4, 0x1CDD5, 0x1CDD6, 0x1CDD7, 0x1CDD8, 0x1CDD9, 0x1CDDA,
    0x02584, 0x1CDDB, 0x1CDDC, 0x1CDDD, 0x1CDDE, 0x02599, 0x1CDDF, 0x1CDE0,
    0x1CDE1, 0x1CDE2, 0x0259F, 0x1CDE3, 0x02586, 0x1CDE4, 0x1CDE5, 0x02588,
))
# fmt: on

Cell = tuple[str, str, str | None] | None


def js_round(value: float) -> int:
    """JavaScript's Math.round: halves go up."""
    return math.floor(value + 0.5)


def linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def to_lab(hex_colour: str) -> list[float]:
    r, g, b = (linear(int(hex_colour[i : i + 2], 16)) for i in (1, 3, 5))
    l = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)  # noqa: E741
    m = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return [
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    ]


def from_lab(lab: list[float]) -> tuple[int, int, int]:
    big_l, a, b = lab
    l = (big_l + 0.3963377774 * a + 0.2158037573 * b) ** 3  # noqa: E741
    m = (big_l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (big_l - 0.0894841775 * a - 1.2914855480 * b) ** 3

    def gamma(v: float) -> int:
        v = min(1.0, max(0.0, v))
        return js_round(
            255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)
        )

    return (
        gamma(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
        gamma(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
        gamma(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
    )


LAB = [(at, to_lab(h)) for at, h in STOPS]


def lab_at(degrees: float) -> list[float]:
    """The colour at an angle, blended in OKLab between the stops either side."""
    degrees = math.fmod(math.fmod(degrees, 360) + 360, 360)
    i = 0
    for k, (at, _) in enumerate(LAB):
        if degrees >= at:
            i = k
    a, start = LAB[i]
    b, end = LAB[(i + 1) % len(LAB)]
    if b <= a:
        b += 360
    t = (degrees - a) / (b - a)
    return [v + (end[n] - v) * t for n, v in enumerate(start)]


def gap(p: list[float], q: list[float]) -> float:
    return sum((v - q[n]) * (v - q[n]) for n, v in enumerate(p))


def ring(window_rows: int) -> list[list[Cell]]:
    """The logo for a window `window_rows` tall: round(window_rows / 5) rows.

    Each cell is None (blank) or (character, foreground, background or None).
    """
    sx, sy = 2, 4
    row_count = js_round(window_rows / 5)
    col_count = 2 * row_count
    nx, ny, bw, bh = col_count * sx, row_count * sy, 1 / sx, 2 / sy
    thickness = THICKNESS_PX / 8
    outer = row_count - 0.125
    inner = outer - thickness

    blocks: list[list[list[float] | None]] = [[None] * nx for _ in range(ny)]
    for j in range(ny):
        for i in range(nx):
            x = (i + 0.5 - nx / 2) * bw
            y = (j + 0.5 - ny / 2) * bh
            r = math.hypot(abs(x), abs(y))
            if r > outer or r < inner:
                continue
            angle = math.atan2(x, -y) * 180 / math.pi
            weave = WEAVE * math.sin(angle * CROSSINGS * math.pi / 180)
            blocks[j][i] = lab_at(angle - TURN + weave)

    rows = []
    for cy in range(row_count):
        line: list[Cell] = []
        for cx in range(col_count):
            # Blocks in reading order: 1 2 / 3 4 / 5 6 / 7 8.
            spots = [
                (j, i)
                for j in range(cy * sy, cy * sy + sy)
                for i in range(cx * sx, cx * sx + sx)
            ]
            covered = [
                (k, j, i) for k, (j, i) in enumerate(spots) if blocks[j][i] is not None
            ]
            if not covered:
                line.append(None)
                continue
            groups = [covered]
            if len(covered) == sx * sy:
                most, far = -1.0, (covered[0], covered[0])
                for p in covered:
                    for q in covered:
                        d = gap(blocks[p[1]][p[2]], blocks[q[1]][q[2]])
                        if d > most:
                            most, far = d, (p, q)
                pa, pb = (blocks[j][i] for _, j, i in far)
                first = [
                    c
                    for c in covered
                    if gap(blocks[c[1]][c[2]], pa) <= gap(blocks[c[1]][c[2]], pb)
                ]
                second = [
                    c
                    for c in covered
                    if gap(blocks[c[1]][c[2]], pa) > gap(blocks[c[1]][c[2]], pb)
                ]
                groups = [g for g in (first, second) if g]
            colours = []
            for group in groups:
                mean = [
                    sum(blocks[j][i][n] for _, j, i in group) / len(group)
                    for n in range(3)
                ]
                colours.append(
                    (
                        "#{:02X}{:02X}{:02X}".format(*from_lab(mean)),
                        {k for k, _, _ in group},
                    )
                )
            # The group holding the first filled block is drawn as the character's
            # foreground; a second group, if any, is its background.
            colours.sort(key=lambda c: min(c[1]))
            fg, fg_blocks = colours[0]
            bg = colours[1][0] if len(colours) == 2 else None
            line.append((OCTANTS[sum(1 << k for k in fg_blocks)], fg, bg))
        rows.append(line)
    return rows


def content(rows: list[list[Cell]]) -> Content:
    """The logo as Textual draws it: plain colour, unset backgrounds left unset."""
    lines = []
    for row in rows:
        parts: list[str | tuple[str, str]] = []
        for cell in row:
            if cell is None:
                parts.append(" ")
            else:
                char, fg, bg = cell
                parts.append((char, f"{fg} on {bg}" if bg else fg))
        lines.append(Content.assemble(*parts))
    return Content("\n").join(lines)
