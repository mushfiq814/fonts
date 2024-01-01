def check_panose_monospaced(font):
    """ Check if the font's Panose flags say it is monospaced """
    # https://forum.high-logic.com/postedfiles/Panose.pdf
    panose = list(font.os2_panose)
    if panose[0] < 2 or panose[0] > 5:
        return -1  # invalid Panose info
    panose_mono = ((panose[0] == 2 and panose[3] == 9) or
                   (panose[0] == 3 and panose[3] == 3))
    return 1 if panose_mono else 0


def panose_check_to_text(value, panose=False):
    """ Convert value from check_panose_monospaced() to human readable string
    """
    if value == 0:
        return "Panose says \"not monospaced\""
    if value == 1:
        return "Panose says \"monospaced\""
    return "Panose is invalid"
    + (" ({})".format(list(panose)) if panose else "")


def is_monospaced(font):
    """ Check if a font is probably monospaced """
    # Some fonts lie (or have not any Panose flag set), spot check monospaced:
    width = -1
    width_mono = True
    # wide and slim glyphs 'I', 'M', 'W', 'a', 'i', 'm', '.'
    for glyph in [0x49, 0x4D, 0x57, 0x61, 0x69, 0x6d, 0x2E]:
        if glyph not in font:
            # A 'strange' font, believe Panose
            return (check_panose_monospaced(font) == 1, None)
        # print(" -> {} {}".format(glyph, font[glyph].width))
        if width < 0:
            width = font[glyph].width
            continue
        if font[glyph].width != width:
            # Exception for fonts like Code New Roman Regular or Hermit
            # Light/Bold:
            # Allow small 'i' and dot to be smaller than normal
            # I believe the source fonts are buggy
            if glyph in [0x69, 0x2E]:
                if width > font[glyph].width:
                    continue
                (xmin, _, xmax, _) = font[glyph].boundingBox()
                if width > xmax - xmin:
                    continue
            width_mono = False
            break
    # We believe our own check more then Panose ;-D
    return (width_mono, None if width_mono else glyph)


def get_advance_width(font, extended, minimum):
    """ Get the maximum/minimum advance width in the extended(?) range """
    width = 0
    if extended:
        end = 0x17f
    else:
        end = 0x07e
    for glyph in range(0x21, end):
        if glyph not in font:
            continue
        if glyph in range(0x7F, 0xBF):
            continue  # ignore special characters like '1/4' etc
        if width == 0:
            width = font[glyph].width
            continue
        if not minimum and width < font[glyph].width:
            width = font[glyph].width
        elif minimum and width > font[glyph].width:
            width = font[glyph].width
    return width


def report_advance_widths(font):
    return "Advance widths (base/extended): {} - {} / {} - {}".format(
        get_advance_width(font, True, True),
        get_advance_width(font, False, True),
        get_advance_width(font, False, False),
        get_advance_width(font, True, False)
    )
