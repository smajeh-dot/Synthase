"""The app's colours: the only place they are written down.

Every token is used as ``$name`` in synthase.tcss and in content markup. The
tokens and their contrast against the background are in
docs/decisions/0016-full-screen-app.md; decision 0027 keeps them for F1.
SYNTHASE_16 is for a console with only 16 colours (decision 0029).
"""

from textual.theme import Theme

SYNTHASE = Theme(
    name="synthase",
    dark=True,
    background="#0C0C0C",
    surface="#0C0C0C",
    panel="#1A1A1A",
    foreground="#CCCCCC",
    primary="#6CB6FF",
    secondary="#A0A0A0",
    accent="#6CB6FF",
    success="#42D55D",
    # Not used in F1.
    warning="#C297FF",
    error="#FC4055",
    variables={
        "echo": "#F2F2F2",
        "heading": "#F2F2F2",
        "muted": "#A0A0A0",
        "status": "#A0A0A0",
        "faint": "#858585",
        "rule": "#767676",
        "line": "#626262",
        "answer": "#6CB6FF",
        # Not used in F1.
        "caution": "#C19C00",
        "select": "#26405C",
        "track": "#141414",
        "thumb": "#767676",
    },
)

# For a console with only 16 colours (decision 0029): each token is the
# nearest Campbell colour, the scheme Windows consoles use, so Rich's step
# down to 16 colours picks the colour meant.
SYNTHASE_16 = Theme(
    name="synthase-16",
    dark=True,
    background="#0C0C0C",
    surface="#0C0C0C",
    panel="#0C0C0C",
    foreground="#CCCCCC",
    primary="#61D6D6",
    secondary="#CCCCCC",
    accent="#61D6D6",
    success="#16C60C",
    # Not used in F1.
    warning="#B4009E",
    error="#E74856",
    variables={
        "echo": "#F2F2F2",
        "heading": "#F2F2F2",
        "muted": "#CCCCCC",
        "status": "#CCCCCC",
        "faint": "#767676",
        "rule": "#767676",
        "line": "#767676",
        "answer": "#61D6D6",
        # Not used in F1.
        "caution": "#C19C00",
        "select": "#0037DA",
        "track": "#0C0C0C",
        "thumb": "#767676",
    },
)
