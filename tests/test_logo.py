# ruff: noqa: E501  (the pinned tables keep one line per row)
"""The start-up logo: the generator against the design's pinned tables.

LOGO_24 and LOGO_30 are the owner-approved design at 80 × 24 and 120 × 30: the
design handoff's ring, made 13 px thick and twisted 40° at the owner's request
(decision 0035). Don't edit them to make a test pass: they are the reference.
"""

from rich.cells import cell_len

from synthase.logo import MIN_ROWS, OCTANTS, js_round, ring

# fmt: off
LOGO_24 = [
    [None, ("\U0001CEA0", "#64B8EE", None), ("\U0001CDE1", "#65BED3", None), ("▆", "#66C1C3", None), ("\U0001FB85", "#67C589", "#67C1C5"), ("\U0001CD26", "#73C365", "#65C58E"), ("▆", "#82C356", None), ("\U0001CDDE", "#B4BD40", None), ("\U0001CEA3", "#DFAD31", None), None],
    [("\U0001CD96", "#4C9DF9", None), ("\U0001CD02", "#57A9F7", "#408EFA"), ("\U0001CD0F", "#499AF9", None), ("\U0001CEA8", "#54A5F8", None), None, None, ("\U0001CEAB", "#77C25C", None), ("\U0001CD22", "#A9C043", None), ("▌", "#DDAF31", "#ED9D2F"), ("\U0001CD48", "#F68B30", None)],
    [("▘", "#408FFA", "#3E85F8"), ("▛", "#4B81F0", "#6377DF"), None, None, None, None, None, None, ("\U0001CD0F", "#EF9B2F", "#F58433"), ("\U0001CD0F", "#F47B35", "#F26739")],
    [("\U0001CD21", "#4881F1", None), ("▌", "#5B7BE6", "#6B74D9"), ("\U0001CDBF", "#836AC2", None), ("\U0001CEA3", "#9660A5", None), None, None, ("\U0001CEA0", "#EF583D", None), ("\U0001CDD3", "#EF603E", None), ("▀", "#F26B38", "#E9544A"), ("\U0001CD0D", "#EC5846", None)],
    [None, ("\U0001CEAB", "#6477DF", None), ("\U0001CD26", "#7670CF", None), ("\U0001FB85", "#8C66B5", None), ("\U0001FB82", "#B65A83", "#9163AD"), ("\U0001CD05", "#D35468", "#9A60A2"), ("\U0001FB85", "#C15A79", None), ("\U0001CD17", "#C55876", None), ("\U0001CEA8", "#D45467", None), None],
]

LOGO_30 = [
    [None, None, ("\U0001CDCB", "#66BFD3", None), ("\U0001CDE1", "#66C0C8", None), ("▆", "#66C3B8", None), ("\U0001FB85", "#67C487", "#68C3BD"), ("▀", "#74C363", "#65C58D"), ("▆", "#77C360", None), ("\U0001CDDE", "#97C248", None), ("\U0001CDBB", "#CCB637", None), None, None],
    [("\U0001CEA0", "#4FA0F8", None), ("\U0001CDE5", "#51A3F8", None), ("\U0001CD70", "#4C9DF9", None), ("\U0001CD02", "#54A6F8", None), None, None, None, None, ("\U0001CD05", "#84C251", None), ("\U0001CDAB", "#B7BD3F", None), ("\U0001CDE4", "#E8A330", None), ("\U0001CEA3", "#F58931", None)],
    [("▟", "#3F8DFA", None), ("\U0001CD17", "#3E86F8", "#4C80EF"), None, None, None, None, None, None, None, None, ("\U0001CD0D", "#E4A730", "#F2952F"), ("▙", "#F47D35", None)],
    [("▜", "#4284F5", None), ("▌", "#547EEA", "#6577DE"), None, None, None, None, None, None, None, None, ("\U0001CD0F", "#F58831", "#F37237"), ("▛", "#F26739", None)],
    [("\U0001CEAB", "#4882F2", None), ("\U0001CDAB", "#5F7AE3", None), ("\U0001CDE4", "#7C6DC9", None), ("\U0001CDBB", "#9163AF", None), None, None, None, None, ("\U0001CDCB", "#ED5942", None), ("\U0001CDE5", "#ED5E43", None), ("\U0001CD70", "#E9574B", None), ("\U0001CEA8", "#EA5549", None)],
    [None, None, ("\U0001CD05", "#6B74D9", None), ("\U0001CD26", "#816BC4", None), ("\U0001FB85", "#9063AF", None), ("\U0001FB82", "#BC597D", "#9262AC"), ("\U0001CD05", "#D0556B", "#9960A3"), ("\U0001FB85", "#BE5A7C", None), ("\U0001CD17", "#C35978", None), ("\U0001CD02", "#C05879", None), None, None],
]
# fmt: on


def test_the_generator_reproduces_the_design_at_80_by_24():
    assert ring(24) == LOGO_24


def test_the_generator_reproduces_the_design_at_120_by_30():
    assert ring(30) == LOGO_30


def test_the_pinned_tables_have_the_design_s_shape():
    for table, rows, filled, backgrounds in ((LOGO_24, 5, 36, 12), (LOGO_30, 6, 40, 8)):
        assert len(table) == rows
        assert all(len(row) == 2 * rows for row in table)
        cells = [cell for row in table for cell in row if cell is not None]
        assert len(cells) == filled
        assert sum(bg is not None for _, _, bg in cells) == backgrounds


def test_every_octant_and_logo_character_is_one_cell_wide():
    assert len(OCTANTS) == 256 and len(set(OCTANTS)) == 256
    used = {
        cell[0] for table in (LOGO_24, LOGO_30) for row in table for cell in row if cell
    }
    assert used <= set(OCTANTS)
    assert all(cell_len(char) == 1 for char in OCTANTS)


def test_halves_round_up_as_the_board_did():
    assert js_round(2.5) == 3
    assert js_round(24 / 5) == 5
    assert js_round(27.5 / 5) == 6


def test_every_height_the_app_draws_gives_a_square_ring():
    for height in range(MIN_ROWS, 61):
        rows = ring(height)
        assert len(rows) == js_round(height / 5)
        assert all(len(row) == 2 * len(rows) for row in rows)
