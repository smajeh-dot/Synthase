# ruff: noqa: E501  (the pinned tables stay exactly as the handoff wrote them)
"""The start-up logo: the generator against the design's pinned tables.

LOGO_24 and LOGO_30 are the owner-approved design at 80 × 24 and 120 × 30,
copied from the design handoff (decision 0035). Don't edit them to make a test
pass: they are the reference.
"""

from rich.cells import cell_len

from synthase.logo import MIN_ROWS, OCTANTS, js_round, ring

# fmt: off
LOGO_24 = [
    [None, ("\U0001CEA0", "#59AAF7", None), ("\U0001CDE1", "#63B8EB", None), ("\U0001CD6D", "#68C3BE", None), ("\U0001FB85", "#66C592", None), ("\U0001FB85", "#67C376", None), ("\U0001CDA8", "#82C252", None), ("\U0001CDDE", "#9CC247", None), ("\U0001CEA3", "#C1BA3B", None), None],
    [("\U0001CD96", "#3F8FFA", None), ("\U0001CD70", "#4899F9", None), ("\U0001CD02", "#59AAF7", None), None, None, None, None, ("\U0001CD05", "#C0BA3B", None), ("\U0001CDAB", "#E3A831", None), ("\U0001CD48", "#EE9C2F", None)],
    [("▀", "#3F84F7", '#4882F2'), ("▌", "#4483F4", None), None, None, None, None, None, None, ("▐", "#F48034", None), ("▀", "#F58732", '#F47836')],
    [("\U0001CD21", "#5B7BE5", None), ("\U0001CDE4", "#6577DE", None), ("\U0001CDBB", "#7570D0", None), None, None, None, None, ("\U0001CDCB", "#E8534D", None), ("\U0001CDE5", "#EF5C3E", None), ("\U0001CD0D", "#F16539", None)],
    [None, ("\U0001CEAB", "#7570D0", None), ("\U0001CD26", "#816BC3", None), ("\U0001CD34", "#8D65B6", None), ("▆", "#9660A5", None), ("▆", "#A05C96", None), ("\U0001CD35", "#C45876", None), ("\U0001CD17", "#DE515B", None), ("\U0001CEA8", "#E8534D", None), None],
]

LOGO_30 = [
    [None, None, ("\U0001CDCB", "#61B4F4", None), ("\U0001CDE1", "#65BED6", None), ("\U0001CD6D", "#69C5AE", None), ("\U0001FB85", "#66C590", None), ("\U0001FB85", "#65C379", None), ("\U0001CDA8", "#79C259", None), ("\U0001CDDE", "#8EC34B", None), ("\U0001CDBB", "#A6C143", None), None, None],
    [("\U0001CEA0", "#4090FA", None), ("\U0001CDE5", "#4A9BF9", None), ("\U0001CD17", "#57A8F7", None), ("\U0001CEA8", "#64B6F6", None), None, None, None, None, ("\U0001CEAB", "#9EC345", None), ("\U0001CD26", "#C6B839", None), ("\U0001CDE4", "#E0AB31", None), ("\U0001CEA3", "#ED9E2F", None)],
    [("▟", "#3E85F8", None), ("\U0001CD4A", "#3E89F9", None), None, None, None, None, None, None, None, None, ("\U0001CD98", "#F39130", None), ("▙", "#F58A31", None)],
    [("▜", "#4B81F0", None), ("\U0001CDC0", "#527FEC", None), None, None, None, None, None, None, None, None, ("\U0001CDD5", "#F36F38", None), ("▛", "#F37537", None)],
    [("\U0001CEAB", "#5D7AE4", None), ("\U0001CDAB", "#6776DC", None), ("\U0001CDDE", "#7371D2", None), ("\U0001CEA3", "#7F6CC6", None), None, None, None, None, ("\U0001CEA0", "#E35056", None), ("\U0001CDE1", "#E9544A", None), ("\U0001CD70", "#EF5A3F", None), ("\U0001CEA8", "#F1633A", None)],
    [None, None, ("\U0001CD05", "#7D6DC7", None), ("\U0001CD26", "#8868BC", None), ("\U0001CD34", "#9063B1", None), ("▆", "#965FA4", None), ("▆", "#9D5C98", None), ("\U0001CD35", "#B85980", None), ("\U0001CD17", "#D35468", None), ("\U0001CD02", "#E45155", None), None, None],
]
# fmt: on


def test_the_generator_reproduces_the_design_at_80_by_24():
    assert ring(24) == LOGO_24


def test_the_generator_reproduces_the_design_at_120_by_30():
    assert ring(30) == LOGO_30


def test_the_pinned_tables_have_the_design_s_shape():
    for table, rows, filled, backgrounds in ((LOGO_24, 5, 32, 2), (LOGO_30, 6, 40, 0)):
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
