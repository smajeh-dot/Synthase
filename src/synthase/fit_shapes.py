"""The curve shapes fit knows, and how many settings each one has to find.

A setting is one number a shape's equation needs, such as a line's slope and
intercept. The count belongs to the equation, not to any measurement, so it
lives here rather than in the config (docs/decisions/0019-fit-check.md).
"""

SHAPES = {
    "line": 2,
    "exponential": 3,
    "s-curve": 4,
    "growth": 4,
    "michaelis-menten": 2,
    "arrhenius": 2,
}
# The checks use this when no shape is chosen, so a file passes only if it
# could be fitted by any of them.
MOST_SETTINGS = max(SHAPES.values())
