import sys
import os
import errno
import fontforge


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


def half_gap(gap, top):
    """ Divides integer value into two new integers """
    # Line gap add extra space on the bottom of the line which
    # doesn't allow the powerline glyphs to fill the entire line.
    # Put half of the gap into the 'cell', each top and bottom
    if gap <= 0:
        return 0
    gap_top = int(gap / 2)
    gap_bottom = gap - gap_top
    if top:
        print("Redistributing line gap of {} ({} top and {} bottom)".format(
            gap, gap_top, gap_bottom))
        return gap_top
    return gap_bottom


def replace_font_name(font_name, replacement_dict):
    """ Replaces all keys with vals from replacement_dict in font_name. """
    for key, val in replacement_dict.items():
        font_name = font_name.replace(key, val)
    return font_name


def make_sure_path_exists(path):
    """ Verifies path passed to it exists. """
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def sanitize_filename(filename, allow_dirs=False):
    """ Enforces to not use forbitten characters in a filename/path. """
    if filename == '.' and not allow_dirs:
        return '_'
    trans = filename.maketrans('<>:"|?*', '_______')
    for i in range(0x00, 0x20):
        trans[i] = ord('_')
    if not allow_dirs:
        trans[ord('/')] = ord('_')
        trans[ord('\\')] = ord('_')
    else:
        trans[ord('\\')] = ord('/')  # We use posix paths
    return filename.translate(trans)


def get_multiglyph_boundingBox(glyphs, destGlyph=None):
    """ Returns dict of the dimensions of multiple glyphs combined(, as if they
    are copied into destGlyph) """
    # If destGlyph is given the glyph(s) are first copied over into that
    # glyph and measured in that font (to avoid rounding errors)
    # Leaves the destGlyph in unknown state!
    bbox = [None, None, None, None, None]
    for glyph in glyphs:
        if glyph is None:
            # Glyph has been in defining range but is not in the actual font
            continue
        if destGlyph:
            glyph.font.selection.select(glyph)
            glyph.font.copy()
            destGlyph.font.selection.select(destGlyph)
            destGlyph.font.paste()
            glyph = destGlyph
        gbb = glyph.boundingBox()
        gadvance = glyph.width
        if len(glyphs) > 1 and gbb[0] == gbb[2] and gbb[1] == gbb[3]:
            # Ignore empty glyphs if we examine more than one glyph
            continue
        bbox[0] = gbb[0] if bbox[0] is None or bbox[0] > gbb[0] else bbox[0]
        bbox[1] = gbb[1] if bbox[1] is None or bbox[1] > gbb[1] else bbox[1]
        bbox[2] = gbb[2] if bbox[2] is None or bbox[2] < gbb[2] else bbox[2]
        bbox[3] = gbb[3] if bbox[3] is None or bbox[3] < gbb[3] else bbox[3]
        if not bbox[4]:
            bbox[4] = -gadvance  # Negative for one/first glyph
        else:
            if abs(bbox[4]) != gadvance:
                bbox[4] = -1  # Marker for not-monospaced
            else:
                bbox[4] = gadvance  # Positive for 2 or more glyphs
    if bbox[4] and bbox[4] < 0:
        # Not monospaced when only one glyph is used or multiple glyphs with
        # different advance widths
        bbox[4] = None
    return {
        'xmin': bbox[0],
        'ymin': bbox[1],
        'xmax': bbox[2],
        'ymax': bbox[3],
        'width': bbox[2] + (-bbox[0]),
        'height': bbox[3] + (-bbox[1]),
        'advance': bbox[4],  # advance width if monospaced
    }


def get_glyph_dimensions(glyph):
    """ Returns dict of the dimesions of the glyph passed to it. """
    return get_multiglyph_boundingBox([glyph])


def scale_bounding_box(bbox, scale_x, scale_y):
    """ Return a scaled version of a glyph dimensions dict """
    # Simulate scaling on combined bounding box, round values for better
    # simulation
    new_dim = {
        'xmin': int(bbox['xmin'] * scale_x),
        'ymin': int(bbox['ymin'] * scale_y),
        'xmax': int(bbox['xmax'] * scale_x),
        'ymax': int(bbox['ymax'] * scale_y),
        'advance': int(bbox['advance'] * scale_x)
        if bbox['advance'] is not None else None,
    }
    new_dim['width'] = new_dim['xmax'] + (-new_dim['xmin'])
    new_dim['height'] = new_dim['ymax'] + (-new_dim['ymin'])
    return new_dim


def update_progress(progress):
    """ Updates progress bar length.

    Accepts a float between 0.0 and 1.0. Any int will be converted to a float.
    A value at 1 or bigger represents 100%
    modified from:
    https://stackoverflow.com/questions/3160699/python-progress-bar
    """
    barLength = 40  # Modify this to change the length of the progress bar
    if isinstance(progress, int):
        progress = float(progress)
    if progress >= 1:
        progress = 1
    block = int(round(barLength * progress))
    text = "\r╢{0}╟ {1}%".format(
        "█" * block + "░" * (barLength - block), int(progress * 100))
    sys.stdout.write(text)
    sys.stdout.flush()


def check_fontforge_min_version():
    """ Verifies installed FontForge version meets minimum requirement. """
    minimumVersion = 20141231
    actualVersion = int(fontforge.version())

    # un-comment following line for testing invalid version error handling
    # actualVersion = 20120731

    # versions tested: 20150612, 20150824
    if actualVersion < minimumVersion:
        sys.stderr.write(
            "You seem to be using an unsupported (old)"
            " version of fontforge: {}\n"
            .format(
                actualVersion
            )
        )
        sys.stderr.write("Please use at least version: {}\n".format(
            minimumVersion))
        sys.exit(1)
