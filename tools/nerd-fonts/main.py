from __future__ import absolute_import, print_function, unicode_literals
import sys
import re
import os
import fontforge
import argparse
from argparse import RawTextHelpFormatter

import TableHEADWriter
import font_patcher
from utils import (
    make_sure_path_exists,
    check_fontforge_min_version,
)


def setup_arguments():
    parser = argparse.ArgumentParser(
        description="script to patch nerd fonts",
        formatter_class=RawTextHelpFormatter
    )

    # optional arguments
    parser.add_argument(
        'font',
        help='The path to the font to patch (e.g., Inconsolata.otf)'
    )
    parser.add_argument(
        '-s',
        '--mono',
        '--use-single-width-glyphs',
        dest='single',
        default=False,
        action='count',
        help='Whether to generate the glyphs as single-width'
             ' not double-width (default is double-width)'
    )
    parser.add_argument(
        '-l',
        '--adjust-line-height',
        dest='adjustLineHeight',
        default=False,
        action='store_true',
        help='Whether to adjust line heights (attempt to center'
             ' powerline separators more evenly)'
    )
    parser.add_argument(
        '-c',
        '--complete',
        dest='complete',
        default=True,
        action='store_true',
        help='Add all available Glyphs'
    )
    parser.add_argument(
        '--careful',
        dest='careful',
        default=False,
        action='store_true',
        help='Do not overwrite existing glyphs if detected'
    )
    parser.add_argument(
        '--configfile',
        dest='configfile',
        default=False,
        type=str,
        nargs='?',
        help='Specify a file path for JSON configuration file'
             ' (see sample: src/config.sample.json)'
    )
    parser.add_argument(
        '-ext',
        '--extension',
        dest='extension',
        default="otf",
        type=str,
        nargs='?',
        help='Change font file type to create(e.g., ttf, otf)'
    )
    parser.add_argument(
        '-out',
        '--outputdir',
        dest='outputdir',
        default=".",
        type=str,
        nargs='?',
        help='The directory to output the patched font file to'
    )
    parser.add_argument(
        '--glyphdir',
        dest='glyphdir',
        default=__dir__ + "/src/glyphs/",
        type=str,
        nargs='?',
        help='Path to glyphs to be used for patching'
    )
    parser.add_argument(
        '--variable-width-glyphs',
        dest='nonmono',
        default=False,
        action='store_true',
        help='Do not adjust advance width(no "overhang")'
    )

    args = parser.parse_args()

    args.progressbars = True

    make_sure_path_exists(args.outputdir)
    if not os.path.isfile(args.font):
        sys.exit("Font file does not exist: %s" % args.font)
    if not os.access(args.font, os.R_OK):
        sys.exit("Can not open font file for reading: %s" % args.font)
    is_ttc = len(fontforge.fontsInFile(args.font)) > 1
    try:
        source_font_test = TableHEADWriter(args.font)
        args.is_variable = source_font_test.find_table(
            [b'avar', b'cvar', b'fvar', b'gvarb', b'HVAR', b'MVAR', b'VVAR'],
            0
        )
        if args.is_variable:
            print(
                "  Warning: Source font is a variable open type font (VF),"
                " opening might fail..."
            )
    except Exception:
        args.is_variable = False
    finally:
        try:
            source_font_test.close()
        except Exception:
            pass

    # TODO: simplify logic
    if re.match(".ttc$", args.extension, re.IGNORECASE):
        if not is_ttc:
            sys.exit(
                ": Can not create True Type Collections"
                + " from single font files"
            )
    else:
        if is_ttc:
            sys.exit(
                ": Can not create single font files"
                + " from True Type Collections"
            )

    return args


def main():
    check_fontforge_min_version()
    args = setup_arguments()
    patcher = font_patcher(args)

    sourceFonts = []
    all_fonts = fontforge.fontsInFile(args.font)
    for i, subfont in enumerate(all_fonts):
        if len(all_fonts) > 1:
            print("\nProcessing {} ({}/{})".format(
                  subfont, i + 1, len(all_fonts)))
        try:
            sourceFonts.append(fontforge.open(
                "{}({})".format(args.font, subfont), 1))
        except Exception:
            sys.exit(
                "Can not open font '{}', try to open with fontforge"
                " interactively to get more information"
                .format(subfont)
            )

        patcher.patch(sourceFonts[-1])

    print("Done with Patch Sets, generating font...")
    patcher.generate(sourceFonts)

    for f in sourceFonts:
        f.close()


if __name__ == "__main__":
    __dir__ = os.path.dirname(os.path.abspath(__file__))
    main()
