from __future__ import absolute_import, print_function, unicode_literals
import sys
import re
import os
import argparse
from argparse import RawTextHelpFormatter
import errno
import subprocess
import json

import TableHEADWriter
from utils import (
    check_panose_monospaced,
    panose_check_to_text,
    is_monospaced,
    report_advance_widths,
)

# Change the script version when you edit this script:
script_version = "3.5.2"

version = "2.3.3"
projectName = "Nerd Fonts"
projectNameAbbreviation = "NF"
projectNameSingular = projectName[:-1]

try:
    import configparser
except ImportError:
    sys.exit("configparser not found!")
try:
    import psMat
    import fontforge
except ImportError:
    sys.exit("fontforge not found!")

sys.path.insert(0, os.path.abspath(os.path.dirname(
    sys.argv[0])) + '/bin/scripts/name_parser/')
try:
    from FontnameParser import FontnameParser
    from FontnameTools import FontnameTools
    FontnameParserOK = True
except ImportError:
    FontnameParserOK = False


class font_patcher:
    def __init__(self, args):
        self.args = args  # class 'argparse.Namespace'
        self.sym_font_args = []
        self.config = None  # class 'configparser.ConfigParser'
        self.sourceFont = None  # class 'fontforge.font'
        self.patch_set = None  # class 'list'
        self.font_dim = None  # class 'dict'
        self.font_extrawide = False
        self.onlybitmaps = 0
        self.essential = set()
        self.config = configparser.ConfigParser(
            empty_lines_in_values=False, allow_no_value=True)

    def patch(self, font):
        self.sourceFont = font
        self.setup_version()
        self.get_essential_references()
        self.setup_name_backup(font)
        if self.args.single:
            self.assert_monospace()
        self.remove_ligatures()
        self.setup_patch_set()
        self.get_sourcefont_dimensions()
        self.improve_line_dimensions()
        # Update the font encoding to ensure that the Unicode glyphs are
        # available
        self.sourceFont.encoding = 'UnicodeFull'
        # Fetch this property before adding outlines. NOTE self.onlybitmaps
        # initialized and never used
        self.onlybitmaps = self.sourceFont.onlybitmaps

        if self.args.single:
            # Force width to be equal on all glyphs to ensure the font is
            # considered monospaced on Windows.
            # This needs to be done on all characters, as some information
            # seems to be lost from the original font file.
            self.set_sourcefont_glyph_widths()
            # For some Windows applications (e.g. 'cmd') that is not enough.
            # But they seem to honour the Panose table
            # https://forum.high-logic.com/postedfiles/Panose.pdf
            panose = list(self.sourceFont.os2_panose)
            # 0 (1st value) = family kind; 0 = any (default); 2 = latin text
            # and display
            if panose[0] == 0 or panose[0] == 2:
                panose[0] = 2  # Assert kind
                panose[3] = 9  # 3 (4th value) = propotion; 9 = monospaced
                self.sourceFont.os2_panose = tuple(panose)

        # For very wide (almost square or wider) fonts we do not want to
        # generate 2 cell wide Powerline glyphs
        if self.font_dim['height'] * 1.8 < self.font_dim['width'] * 2:
            print(
                "Very wide and short font, disabling 2 cell Powerline glyphs"
            )
            self.font_extrawide = True

        # Prevent opening and closing the fontforge font. Makes things faster
        # when patching
        # multiple ranges using the same symbol font.
        PreviousSymbolFilename = ""
        symfont = None

        if not os.path.isdir(self.args.glyphdir):
            sys.exit(
                "{}: Can not find symbol glyph directory {} "
                "(probably you need to download the src/glyphs/ directory?)"
                .format(projectName, self.args.glyphdir)
            )

        for patch in self.patch_set:
            if patch['Enabled']:
                if PreviousSymbolFilename != patch['Filename']:
                    # We have a new symbol font, so close the previous one if
                    # it exists
                    if symfont:
                        symfont.close()
                        symfont = None
                    if not os.path.isfile(
                        self.args.glyphdir + patch['Filename']
                    ):
                        sys.exit(
                            "{}: Can not find symbol source for"
                            "'{}'\n{:>{}}  (i.e. {})"
                            .format(
                                projectName,
                                patch['Name'],
                                '',
                                len(projectName),
                                self.args.glyphdir + patch['Filename']
                            )
                        )
                    if not os.access(
                        self.args.glyphdir + patch['Filename'],
                        os.R_OK
                    ):
                        sys.exit(
                            "{}: Can not open symbol source for '{}'\n{:>{}} "
                            " (i.e. {})"
                            .format(
                                projectName,
                                patch['Name'],
                                '',
                                len(projectName),
                                self.args.glyphdir + patch['Filename']
                            )
                        )
                    symfont = fontforge.open(os.path.join(
                        self.args.glyphdir, patch['Filename']))

                    # Match the symbol font size to the source font size
                    symfont.em = self.sourceFont.em
                    PreviousSymbolFilename = patch['Filename']

                # If patch table doesn't include a source start, re-use the
                # symbol font values
                SrcStart = patch['SrcStart']
                if not SrcStart:
                    SrcStart = patch['SymStart']
                self.copy_glyphs(
                    SrcStart,
                    symfont,
                    patch['SymStart'],
                    patch['SymEnd'],
                    patch['Exact'],
                    patch['ScaleRules'],
                    patch['Name'],
                    patch['Attributes']
                )

        if symfont:
            symfont.close()

        # The grave accent and fontforge:
        # If the type is 'auto' fontforge changes it to 'mark' on export.
        # We can not prevent this. So set it to 'baseglyph' instead, as
        # that resembles the most common expectations.
        # This is not needed with fontforge March 2022 Release anymore.
        if "grave" in self.sourceFont:
            self.sourceFont["grave"].glyphclass = "baseglyph"

    def generate(self, sourceFonts):
        sourceFont = sourceFonts[0]
        # the `PfEd-comments` flag is required for Fontforge to save '.comment'
        # and '.fontlog'.
        if int(fontforge.version()) >= 20201107:
            gen_flags = (str('opentype'), str(
                'PfEd-comments'), str('no-FFTM-table'))
        else:
            gen_flags = (str('opentype'), str('PfEd-comments'))
        if len(sourceFonts) > 1:
            layer = None
            # use first non-background layer
            for l in sourceFont.layers:
                if not sourceFont.layers[l].is_background:
                    layer = l
                    break
            outfile = os.path.normpath(os.path.join(
                sanitize_filename(self.args.outputdir, True),
                sanitize_filename(sourceFont.familyname) + ".ttc"))
            sourceFonts[0].generateTtc(
                outfile, sourceFonts[1:], flags=gen_flags, layer=layer)
            message = "   Generated {} fonts\n   \===> '{}'".format(
                len(sourceFonts), outfile)
        else:
            fontname = sourceFont.fullname
            if not fontname:
                fontname = sourceFont.cidfontname
            outfile = os.path.normpath(os.path.join(
                sanitize_filename(self.args.outputdir, True),
                sanitize_filename(fontname) + self.args.extension))
            bitmaps = str()
            if len(self.sourceFont.bitmapSizes):
                if not self.args.quiet:
                    print("Preserving bitmaps {}".format(
                        self.sourceFont.bitmapSizes))
                bitmaps = str('otf')  # otf/ttf, both is bf_ttf
            sourceFont.generate(outfile, bitmap_type=bitmaps, flags=gen_flags)
            message = "   {}\n   \===> '{}'".format(
                self.sourceFont.fullname, outfile)

        # Adjust flags that can not be changed via fontforge
        if re.search(
            '\\.[ot]tf$', self.args.font, re.IGNORECASE
        ) and re.search(
            '\\.[ot]tf$', outfile, re.IGNORECASE
        ):
            try:
                source_font = TableHEADWriter(self.args.font)
                dest_font = TableHEADWriter(outfile)
                for idx in range(source_font.num_fonts):
                    if not self.args.quiet:
                        print("{}: Tweaking {}/{}".format(projectName,
                              idx + 1, source_font.num_fonts))
                    source_font.find_head_table(idx)
                    dest_font.find_head_table(idx)
                    if (
                        (
                            source_font.flags & 0x08 == 0
                        ) and (
                            dest_font.flags & 0x08 != 0
                        )
                    ):
                        if not self.args.quiet:
                            print(
                                "Changing flags from 0x{:X} to 0x{:X}"
                                .format(
                                    dest_font.flags, dest_font.flags & ~0x08
                                )
                            )
                        # clear 'ppem_to_int'
                        dest_font.putshort(dest_font.flags & ~0x08, 'flags')
                    if source_font.lowppem != dest_font.lowppem:
                        if not self.args.quiet:
                            print(
                                "Changing lowestRecPPEM from {} to {}"
                                .format(dest_font.lowppem, source_font.lowppem)
                            )
                        dest_font.putshort(
                            source_font.lowppem, 'lowestRecPPEM')
                    if dest_font.modified:
                        dest_font.reset_table_checksum()
                        dest_font.reset_full_checksum()
            except Exception as error:
                print("Can not handle font flags ({})".format(repr(error)))
            finally:
                try:
                    source_font.close()
                    dest_font.close()
                except:
                    pass
        if self.args.is_variable:
            print(
                "Warning: Source font is a variable open type font (VF)"
                " and the patch results will most likely not be what you want"
            )
        print(message)

        if self.args.postprocess:
            subprocess.call([self.args.postprocess, outfile])
            print("\nPost Processed: {}".format(outfile))

    def setup_name_backup(self, font):
        """ Store the original font names to be able to rename the font
        multiple times """
        font.persistent = {
            "fontname": font.fontname,
            "fullname": font.fullname,
            "familyname": font.familyname,
        }

    def setup_version(self):
        """ Add the Nerd Font version to the original version """
        # print("Version was {}".format(sourceFont.version))
        if self.sourceFont.version is not None:
            self.sourceFont.version += ";" + projectName + " " + version
        else:
            self.sourceFont.version = str(
                self.sourceFont.cidversion) + ";" + projectName + " " + version
        # Auto-set (refreshed) by fontforge
        self.sourceFont.sfntRevision = None
        self.sourceFont.appendSFNTName(str('English (US)'), str(
            'Version'), "Version " + self.sourceFont.version)
        # print("Version now is {}".format(sourceFont.version))

    def remove_ligatures(self):
        # let's deal with ligatures (mostly for monospaced fonts)
        # the tables have been removed from the repo with >this< commit
        if self.args.configfile and self.config.read(self.args.configfile):
            if self.args.removeligatures:
                print("Removing ligatures from configfile `Subtables` section")
                ligature_subtables = json.loads(
                    self.config.get("Subtables", "ligatures"))
                for subtable in ligature_subtables:
                    print("Removing subtable:", subtable)
                    try:
                        self.sourceFont.removeLookupSubtable(subtable)
                        print("Successfully removed subtable:", subtable)
                    except Exception:
                        print("Failed to remove subtable:", subtable)
        elif self.args.removeligatures:
            print("Unable to read configfile, unable to remove ligatures")

    def assert_monospace(self):
        # Check if the sourcefont is monospaced
        width_mono, offending_char = is_monospaced(self.sourceFont)
        panose_mono = check_panose_monospaced(self.sourceFont)
        # The following is in fact "width_mono != panose_mono", but only if
        # panose_mono is not 'unknown'
        if (
            width_mono and panose_mono == 0
        ) or (
            not width_mono and panose_mono == 1
        ):
            print("  Warning: Monospaced check: Panose assumed to be wrong")
            print("  {} and {}".format(
                report_advance_widths(self.sourceFont),
                panose_check_to_text(panose_mono, self.sourceFont.os2_panose)))
        if not width_mono:
            print(
                "  Warning: Sourcefont is not monospaced - forcing"
                " to monospace not advisable, results might be useless"
            )
            if offending_char is not None:
                print("           Offending char: 0x{:X}".format(
                    offending_char))
            if self.args.single <= 1:
                sys.exit(
                    projectName +
                    ": Font will not be patched! Give --mono (or -s, or"
                    " --use-single-width-glyphs) twice to force patching"
                )

    def setup_patch_set(self):
        """ Creates list of dicts to with instructions on copying glyphs from
        each symbol font into self.sourceFont """
        # Supported params: overlap | careful
        # Overlap value is used horizontally but vertically limited to 0.01
        # Powerline dividers
        SYM_ATTR_POWERLINE = {
            'default': {
                'align': 'c',
                'valign': 'c',
                'stretch': 'pa',
                'params': {}
            },

            # Arrow tips
            0xe0b0: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.02,
                    'xy-ratio': 0.7
                }
            },
            0xe0b1: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'xy-ratio': 0.7
                }
            },
            0xe0b2: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.02,
                    'xy-ratio': 0.7
                }
            },
            0xe0b3: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'xy-ratio': 0.7
                }
            },

            # Rounded arcs
            0xe0b4: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.01,
                    'xy-ratio': 0.59
                }
            },
            0xe0b5: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'xy-ratio': 0.5
                }
            },
            0xe0b6: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.01,
                    'xy-ratio': 0.59
                }
            },
            0xe0b7: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'xy-ratio': 0.5
                }
            },

            # Bottom Triangles
            0xe0b8: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.02
                }
            },
            0xe0b9: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {}
            },
            0xe0ba: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.02
                }
            },
            0xe0bb: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {}
            },

            # Top Triangles
            0xe0bc: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.02
                }
            },
            0xe0bd: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {}
            },
            0xe0be: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.02
                }
            },
            0xe0bf: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {}
            },

            # Flames
            0xe0c0: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.01
                }
            },
            0xe0c1: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {}
            },
            0xe0c2: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.01
                }
            },
            0xe0c3: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {}
            },

            # Small squares
            0xe0c4: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {}
            },
            0xe0c5: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy',
                'params': {}
            },

            # Bigger squares
            0xe0c6: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {}
            },
            0xe0c7: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy',
                'params': {}
            },

            # Waveform
            0xe0c8: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.01
                }
            },
            0xe0ca: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy2',
                'params': {
                    'overlap': 0.01
                }
            },

            # Hexagons
            0xe0cc: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.02
                }
            },
            0xe0cd: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {}
            },

            # Legos
            0xe0ce: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {}
            },
            0xe0cf: {
                'align': 'c',
                'valign': 'c',
                'stretch': 'xy',
                'params': {}
            },
            0xe0d1: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.02
                }
            },

            # Top and bottom trapezoid
            0xe0d2: {
                'align': 'l',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.02,
                    'xy-ratio': 0.7
                }
            },
            0xe0d4: {
                'align': 'r',
                'valign': 'c',
                'stretch': 'xy',
                'params': {
                    'overlap': 0.02,
                    'xy-ratio': 0.7
                }
            }
        }

        SYM_ATTR_DEFAULT = {
            # 'pa' == preserve aspect ratio
            'default': {
                'align': 'c',
                'valign': 'c',
                'stretch': 'pa',
                'params': {}
            }
        }

        SYM_ATTR_FONTA = {
            # 'pa' == preserve aspect ratio
            'default': {
                'align': 'c',
                'valign': 'c',
                'stretch': 'pa',
                'params': {}
            },

            # Don't center these arrows vertically
            0xf0dc: {
                'align': 'c',
                'valign': '',
                'stretch': 'pa',
                'params': {}
            },
            0xf0dd: {
                'align': 'c',
                'valign': '',
                'stretch': 'pa',
                'params': {}
            },
            0xf0de: {
                'align': 'c',
                'valign': '',
                'stretch': 'pa',
                'params': {}
            }
        }

        CUSTOM_ATTR = {
            # 'pa' == preserve aspect ratio
            'default': {
                'align': 'c',
                'valign': '',
                'stretch': '',
                'params': {}
            }
        }

        # Most glyphs we want to maximize (individually) during the scale
        # However, there are some that need to be small or stay relative in
        # size to each other.
        # The glyph-specific behavior can be given as ScaleRules in the
        # patch-set.
        #
        # ScaleRules can contain two different kind of rules (possibly in
        # parallel):
        #   - ScaleGlyph:
        #       Here one specific glyph is used as 'scale blueprint'. Other
        #       glyphs are
        #       scaled by the same factor as this glyph. This is useful if you
        #       have one
        #       'biggest' glyph and all others should stay relatively in size.
        #       Shifting in addition to scaling can be selected too (see
        #       below).
        #   - ScaleGroups:
        #       Here you specify a group of glyphs that should be handled
        #       together
        #       with the same scaling and shifting. The basis for it is a
        #       'combined
        #       bounding box' of all glyphs in that group. All glyphs are
        #       handled as
        #       if they fill that combined bounding box.
        #
        # The ScaleGlyph method: You set 'ScaleGlyph' to the unicode of the
        # reference glyph.
        # Note that there can be only one per patch-set.
        # Additionally you set 'GlyphsToScale' that contains all the glyphs
        # that shall be
        # handled (scaled) like the reference glyph.
        # It is a List of: ((glyph code) or (tuple of two glyph codes that form
        # a closed range))
        #    'GlyphsToScale': [
        #        0x0100, 0x0300, 0x0400,  # The single glyphs 0x0100, 0x0300,
        #        and 0x0400
        #        (0x0200, 0x0210),        # All glyphs 0x0200 to 0x0210
        #        including both 0x0200 and 0x0210
        #    ]}
        # If you want to not only scale but also shift as the refenerce glyph
        # you give the
        # data as 'GlyphsToScale+'. Note that only one set is used and the plus
        # version is preferred.
        #
        # For the ScaleGroup method you define any number groups of glyphs and
        # each group is
        # handled separately. The combined bounding box of all glyphs in the
        # group is determined
        # and based on that the scale and shift for all the glyphs in the
        # group.
        # You define the groups as value of 'ScaleGroups'.
        # It is a List of: ((lists of glyph codes) or (ranges of glyph codes))
        #    'ScaleGroups': [
        #        [0x0100, 0x0300, 0x0400],  # One group consists of glyphs
        #        0x0100, 0x0300, and 0x0400
        #        range(0x0200, 0x0210 + 1), # Another group contains glyphs
        #        0x0200 to 0x0210 incl.
        #
        # Note the subtle differences: tuple vs. range; closed vs open range;
        # etc
        # See prepareScaleRules() for some more details.
        # For historic reasons ScaleGroups is sometimes called 'new method' and
        # ScaleGlyph 'old'.
        # The codepoints mentioned here are symbol-font-codepoints.

        DEVI_SCALE_LIST = {
            'ScaleGlyph': 0xE60E,  # Android logo
            'GlyphsToScale': [
                (0xe6bd, 0xe6c3)  # very small things
            ]
        }
        FONTA_SCALE_LIST = {
            'ScaleGroups': [
                [0xf005, 0xf006, 0xf089],  # star, star empty, half star
                range(0xf026, 0xf028 + 1),  # volume off, down, up
                range(0xf02b, 0xf02c + 1),  # tag, tags
                range(0xf031, 0xf035 + 1),  # font et al
                range(0xf044, 0xf046 + 1),  # edit, share, check (boxes)
                range(0xf048, 0xf052 + 1),  # multimedia buttons
                range(0xf060, 0xf063 + 1),  # arrows
                [0xf053, 0xf054, 0xf077, 0xf078],  # chevron all directions
                range(0xf07d, 0xf07e + 1),  # resize
                range(0xf0a4, 0xf0a7 + 1),  # pointing hands
                # caret all directions and same looking sort
                [0xf0d7, 0xf0d8, 0xf0d9, 0xf0da, 0xf0dc, 0xf0dd, 0xf0de],
                range(0xf100, 0xf107 + 1),  # angle
                range(0xf130, 0xf131 + 1),  # mic
                range(0xf141, 0xf142 + 1),  # ellipsis
                range(0xf153, 0xf15a + 1),  # currencies
                range(0xf175, 0xf178 + 1),  # long arrows
                range(0xf182, 0xf183 + 1),  # male and female
                range(0xf221, 0xf22d + 1),  # gender or so
                range(0xf255, 0xf25b + 1),  # hand symbols
            ]
        }
        OCTI_SCALE_LIST = {
            'ScaleGlyph': 0xF02E,  # looking glass (probably biggest glyph?)
            'GlyphsToScale': [
                (0xf03d, 0xf040),  # arrows
                0xf044, 0xf05a, 0xf05b, 0xf0aa,  # triangles
                (0xf051, 0xf053),  # small stuff
                0xf071, 0xf09f, 0xf0a0, 0xf0a1,  # small arrows
                0xf078, 0xf0a2, 0xf0a3, 0xf0a4,  # chevrons
                0xf0ca,  # dash
            ]
        }
        WEATH_SCALE_LIST = {
            'ScaleGroups': [
                range(0xf095, 0xf0b0 + 1),  # moon phases
                range(0xf0b7, 0xf0c3 + 1),  # wind strengths
                range(0xf053, 0xf055 + 1),  # thermometer
                [0xf06e, 0xf070],  # solar eclipse
                [0xf042, 0xf045],  # degree sign
            ]
        }
        MDI_SCALE_LIST = {
            'ScaleGlyph': 0xf068d,  # 'solid' fills complete design space
            'GlyphsToScale+': [
                # all because they are very well scaled already
                (0xf0000, 0xfffff)
            ]
        }

        # Define the character ranges
        # Symbol font ranges
        self.patch_set = [
            {
                'Enabled': True,
                'Name': "Seti-UI + Custom",
                'Filename': "original-source.otf",

                'Exact': False,
                'SymStart': 0xE4FA,
                'SymEnd': 0xE5AA,
                'SrcStart': 0xE5FA,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': True,
                'Name': "Devicons",
                'Filename': "devicons.ttf",

                'Exact': False,
                'SymStart': 0xE600,
                'SymEnd': 0xE6C5,
                'SrcStart': 0xE700,
                'ScaleRules': DEVI_SCALE_LIST,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': self.args.powerline,
                'Name': "Powerline Symbols",
                'Filename': "powerline-symbols/PowerlineSymbols.otf",

                'Exact': True,
                'SymStart': 0xE0A0,
                'SymEnd': 0xE0A2,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_POWERLINE
            },
            {
                'Enabled': self.args.powerline,
                'Name': "Powerline Symbols",
                'Filename': "powerline-symbols/PowerlineSymbols.otf",

                'Exact': True,
                'SymStart': 0xE0B0,
                'SymEnd': 0xE0B3,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_POWERLINE
            },
            {
                'Enabled': self.args.powerlineextra,
                'Name': "Powerline Extra Symbols",
                'Filename': "PowerlineExtraSymbols.otf",

                'Exact': True,
                'SymStart': 0xE0A3,
                'SymEnd': 0xE0A3,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_POWERLINE
            },
            {
                'Enabled': self.args.powerlineextra,
                'Name': "Powerline Extra Symbols",
                'Filename': "PowerlineExtraSymbols.otf",

                'Exact': True,
                'SymStart': 0xE0B4,
                'SymEnd': 0xE0C8,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_POWERLINE
            },
            {
                'Enabled': self.args.powerlineextra,
                'Name': "Powerline Extra Symbols",
                'Filename': "PowerlineExtraSymbols.otf",

                'Exact': True,
                'SymStart': 0xE0CA,
                'SymEnd': 0xE0CA,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_POWERLINE
            },
            {
                'Enabled': self.args.powerlineextra,
                'Name': "Powerline Extra Symbols",
                'Filename': "PowerlineExtraSymbols.otf",

                'Exact': True,
                'SymStart': 0xE0CC,
                'SymEnd': 0xE0D4,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_POWERLINE
            },
            {
                'Enabled': self.args.pomicons,
                'Name': "Pomicons",
                'Filename': "Pomicons.otf",

                'Exact': True,
                'SymStart': 0xE000,
                'SymEnd': 0xE00A,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': self.args.fontawesome,
                'Name': "Font Awesome",
                'Filename': "font-awesome/FontAwesome.otf",

                'Exact': True,
                'SymStart': 0xF000,
                'SymEnd': 0xF2E0,
                'SrcStart': None,
                'ScaleRules': FONTA_SCALE_LIST,
                'Attributes': SYM_ATTR_FONTA
            },
            {
                'Enabled': self.args.fontawesomeextension,
                'Name': "Font Awesome Extension",
                'Filename': "font-awesome-extension.ttf",

                'Exact': False,
                'SymStart': 0xE000,
                'SymEnd': 0xE0A9,

                'SrcStart': 0xE200,
                'ScaleRules': None,
                'Attributes':
                SYM_ATTR_DEFAULT
            },
            # Maximize
            {
                'Enabled': self.args.powersymbols,
                'Name': "Power Symbols",
                'Filename': "Unicode_IEC_symbol_font.otf",
                'Exact': True,

                'SymStart': 0x23FB,
                'SymEnd': 0x23FE,
                'SrcStart': None,

                'ScaleRules': None,
                'Attributes': SYM_ATTR_DEFAULT
            },
            # Power, Power On/Off, Power On, Sleep
            {
                'Enabled': self.args.powersymbols,
                'Name': "Power Symbols",
                'Filename': "Unicode_IEC_symbol_font.otf",
                'Exact': True,

                'SymStart': 0x2B58,
                'SymEnd': 0x2B58,
                'SrcStart': None,

                'ScaleRules': None,
                'Attributes': SYM_ATTR_DEFAULT
            },
            # Heavy Circle (aka Power Off)
            {
                'Enabled': self.args.material,
                'Name': "Material legacy",
                'Filename': "materialdesignicons-webfont.ttf",

                'Exact': False,
                'SymStart': 0xF001,
                'SymEnd': 0xF847,
                'SrcStart': 0xF500,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': self.args.material,
                'Name': "Material",
                'Filename': "materialdesign/MaterialDesignIconsDesktop.ttf",

                'Exact': True,
                'SymStart': 0xF0001,
                'SymEnd': 0xF1AF0,
                'SrcStart': None,
                'ScaleRules': MDI_SCALE_LIST,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': self.args.weather,
                'Name': "Weather Icons",
                'Filename': "weather-icons/weathericons-regular-webfont.ttf",

                'Exact': False,
                'SymStart': 0xF000,
                'SymEnd': 0xF0EB,
                'SrcStart': 0xE300,
                'ScaleRules': WEATH_SCALE_LIST,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': self.args.fontlogos,
                'Name': "Font Logos",
                'Filename': "font-logos.ttf",

                'Exact': True,
                'SymStart': 0xF300,
                'SymEnd': 0xF32F,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': self.args.octicons,
                'Name': "Octicons",
                'Filename': "octicons.ttf",
                'Exact': False,

                'SymStart': 0xF000,
                'SymEnd': 0xF105,
                'SrcStart': 0xF400,

                'ScaleRules': OCTI_SCALE_LIST,
                'Attributes': SYM_ATTR_DEFAULT
            },
            # Magnifying glass
            {
                'Enabled': self.args.octicons,
                'Name': "Octicons",
                'Filename': "octicons.ttf",

                'Exact': True,
                'SymStart': 0x2665,
                'SymEnd': 0x2665,

                'SrcStart': None,
                'ScaleRules': OCTI_SCALE_LIST,
                'Attributes':
                SYM_ATTR_DEFAULT
            },
            # Heart
            {
                'Enabled': self.args.octicons,
                'Name': "Octicons",
                'Filename': "octicons.ttf",

                'Exact': True,
                'SymStart': 0X26A1,
                'SymEnd': 0X26A1,

                'SrcStart': None,
                'ScaleRules': OCTI_SCALE_LIST,
                'Attributes':
                SYM_ATTR_DEFAULT
            },
            # Zap
            {
                'Enabled': self.args.octicons,
                'Name': "Octicons",
                'Filename': "octicons.ttf",

                'Exact': False,
                'SymStart': 0xF27C,
                'SymEnd': 0xF27C,

                'SrcStart': 0xF4A9,
                'ScaleRules': OCTI_SCALE_LIST,
                'Attributes':
                SYM_ATTR_DEFAULT
            },
            # Desktop
            {
                'Enabled': self.args.codicons,
                'Name': "Codicons",
                'Filename': "codicons/codicon.ttf",

                'Exact': True,
                'SymStart': 0xEA60,
                'SymEnd': 0xEBEB,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': SYM_ATTR_DEFAULT
            },
            {
                'Enabled': self.args.custom,
                'Name': "Custom",
                'Filename': self.args.custom,

                'Exact': True,
                'SymStart': 0x0000,
                'SymEnd': 0x0000,
                'SrcStart': None,
                'ScaleRules': None,
                'Attributes': CUSTOM_ATTR
            }
        ]

    def improve_line_dimensions(self):
        # Make the total line size even.  This seems to make the powerline
        # separators center more evenly.
        if self.args.adjustLineHeight:
            if (
                self.sourceFont.os2_winascent + self.sourceFont.os2_windescent
            ) % 2 != 0:
                # All three are equal before due to get_sourcefont_dimensions()
                self.sourceFont.hhea_ascent += 1
                self.sourceFont.os2_typoascent += 1
                self.sourceFont.os2_winascent += 1

    def add_glyphrefs_to_essential(self, unicode):
        self.essential.add(unicode)
        # According to fontforge spec, altuni is either None or a tuple of
    # tuples
        # Those tuples contained in altuni are of the following "format":
        # (unicode-value, variation-selector, reserved-field)
        altuni = self.sourceFont[unicode].altuni
        if altuni is not None:
            for altcode in [v for v, s, r in altuni if v >= 0]:
                # If alternate unicode already exists in self.essential,
                # that means it has gone through this function before.
                # Therefore we skip it to avoid infinite loop.
                # A unicode value of -1 basically means unused and is also
                # worth skipping.
                if altcode not in self.essential:
                    self.add_glyphrefs_to_essential(altcode)
        # From fontforge documentation:
        # glyph.references return a tuple of tuples containing, for each
        # reference in foreground, a glyph name, a transformation matrix, and
        # whether the reference is currently selected.
        references = self.sourceFont[unicode].references
        for refcode in [self.sourceFont[n].unicode for n, m, s in references]:
            if refcode not in self.essential and refcode >= 0:
                self.add_glyphrefs_to_essential(refcode)

    def get_essential_references(self):
        """Find glyphs that are needed for the basic glyphs"""
        # Sometimes basic glyphs are constructed from multiple other glyphs.
        # Find out which other glyphs are also needed to keep the basic
        # glyphs intact.
        # 0x00-0x17f is the Latin Extended-A range
        basic_glyphs = set()
        # Collect substitution destinations
        for glyph in range(0x21, 0x17f + 1):
            if glyph not in self.sourceFont:
                continue
            basic_glyphs.add(glyph)
            for possub in self.sourceFont[glyph].getPosSub('*'):
                if possub[1] == 'Substitution' or possub[1] == 'Ligature':
                    basic_glyphs.add(self.sourceFont[possub[2]].unicode)
        basic_glyphs.discard(-1)  # the .notdef glyph
        for glyph in basic_glyphs:
            self.add_glyphrefs_to_essential(glyph)

    def get_sourcefont_dimensions(self):
        """ This gets the font dimensions (cell width and height), and makes
        them equal on all platforms """
        # Step 1
        # There are three ways to discribe the baseline to baseline distance
        # (a.k.a. line spacing) of a font. That is all a kuddelmuddel
        # and we try to sort this out here
        # See also https://glyphsapp.com/learn/vertical-metrics
        # See also https://github.com/source-foundry/font-line
        hhea_height = (
            self.sourceFont.hhea_ascent - self.sourceFont.hhea_descent
        )
        typo_height = (
            self.sourceFont.os2_typoascent - self.sourceFont.os2_typodescent
        )
        win_height = (
            self.sourceFont.os2_winascent + self.sourceFont.os2_windescent
        )
        win_gap = max(
            0,
            self.sourceFont.hhea_linegap - win_height + hhea_height
        )
        hhea_btb = hhea_height + self.sourceFont.hhea_linegap
        typo_btb = typo_height + self.sourceFont.os2_typolinegap
        win_btb = win_height + win_gap
        use_typo = self.sourceFont.os2_use_typo_metrics != 0

        # We use either TYPO (1) or WIN (2) and compare with HHEA
        # and use HHEA (0) if the fonts seems broken
        our_btb = typo_btb if use_typo else win_btb
        if our_btb == hhea_btb:
            metrics = 1 if use_typo else 2  # conforming font
        else:
            # We trust the WIN metric more, see experiments in #1056
            print(
                "{}: WARNING Font vertical metrics inconsistent"
                " (HHEA {} / TYPO {} / WIN {}), using WIN"
                .format(projectName, hhea_btb, typo_btb, win_btb)
            )
            our_btb = win_btb
            metrics = 1

        # print("FINI hhea {} typo {} win {} use {}     {}
    # {}".format(hhea_btb, typo_btb, win_btb, use_typo, our_btb != hhea_btb,
    # self.sourceFont.fontname))

        self.font_dim = {'xmin': 0, 'ymin': 0, 'xmax': 0,
                         'ymax': 0, 'width': 0, 'height': 0}

        if metrics == 0:
            self.font_dim['ymin'] = self.sourceFont.hhea_descent + \
                half_gap(self.sourceFont.hhea_linegap, False)
            self.font_dim['ymax'] = self.sourceFont.hhea_ascent + \
                half_gap(self.sourceFont.hhea_linegap, True)
        elif metrics == 1:
            self.font_dim['ymin'] = self.sourceFont.os2_typodescent + \
                half_gap(self.sourceFont.os2_typolinegap, False)
            self.font_dim['ymax'] = self.sourceFont.os2_typoascent + \
                half_gap(self.sourceFont.os2_typolinegap, True)
        else:
            self.font_dim['ymin'] = - \
                self.sourceFont.os2_windescent + half_gap(win_gap, False)
            self.font_dim['ymax'] = self.sourceFont.os2_winascent + \
                half_gap(win_gap, True)

        # Calculate font height
        self.font_dim['height'] = - \
            self.font_dim['ymin'] + self.font_dim['ymax']
        if self.font_dim['height'] == 0:
            # This can only happen if the input font is empty
            # Assume we are using our prepared templates
            self.font_dim = {
                'xmin': 0,
                'ymin': -self.sourceFont.descent,
                'xmax': self.sourceFont.em,
                'ymax': self.sourceFont.ascent,
                'width': self.sourceFont.em,
                'height': self.sourceFont.descent + self.sourceFont.ascent,
            }
        elif self.font_dim['height'] < 0:
            sys.exit("{}: Can not detect sane font height".format(projectName))

        # Make all metrics equal
        self.sourceFont.os2_typolinegap = 0
        self.sourceFont.os2_typoascent = self.font_dim['ymax']
        self.sourceFont.os2_typodescent = self.font_dim['ymin']
        self.sourceFont.os2_winascent = self.sourceFont.os2_typoascent
        self.sourceFont.os2_windescent = -self.sourceFont.os2_typodescent
        self.sourceFont.hhea_ascent = self.sourceFont.os2_typoascent
        self.sourceFont.hhea_descent = self.sourceFont.os2_typodescent
        self.sourceFont.hhea_linegap = self.sourceFont.os2_typolinegap
        self.sourceFont.os2_use_typo_metrics = 1

        # Step 2
        # Find the biggest char width and advance width
        # 0x00-0x17f is the Latin Extended-A range
        # Do not warn if quiet or proportional target
        warned = self.args.quiet or self.args.nonmono
        for glyph in range(0x21, 0x17f):
            if glyph in range(0x7F, 0xBF) or glyph in [
                    0x132, 0x133,  # IJ, ij (in Overpass Mono)
                    # Single and double quotes in Inconsolata LGC
                    0x022, 0x027, 0x060,
                    # Eth and others with stroke or caron in RobotoMono
                    0x0D0, 0x10F, 0x110, 0x111, 0x127, 0x13E, 0x140, 0x165,
                    0x02D,  # hyphen for Monofur
            ]:
                # ignore special characters like '1/4' etc and some specifics
                continue
            try:
                (_, _, xmax, _) = self.sourceFont[glyph].boundingBox()
            except TypeError:
                continue
            if self.font_dim['width'] < self.sourceFont[glyph].width:
                self.font_dim['width'] = self.sourceFont[glyph].width
                # NOT 'basic' glyph, which includes a-zA-Z
                if not warned and glyph > 0x7a:
                    print(
                        "Warning: Extended glyphs wider than basic glyphs,"
                        " results might be useless\n  {}"
                        .format(report_advance_widths(self.sourceFont))
                    )
                    warned = True
            if xmax > self.font_dim['xmax']:
                self.font_dim['xmax'] = xmax
        # print("FINAL", self.font_dim)

    def get_scale_factors(self, sym_dim, stretch):
        """ Get scale in x and y as tuple """
        # It is possible to have empty glyphs, so we need to skip those.
        if not sym_dim['width'] or not sym_dim['height']:
            return (1.0, 1.0)

        # For monospaced fonts all chars need to be maximum 'one' space wide
        # other fonts allows double width glyphs for 'pa' or if requested with
    # '2'
        if self.args.single or (stretch != 'pa' and '2' not in stretch):
            relative_width = 1.0
        else:
            relative_width = 2.0
        target_width = self.font_dim['width'] * relative_width
        scale_ratio_x = target_width / sym_dim['width']

        # font_dim['height'] represents total line height, keep our symbols
    # sized based upon font's em
        # Use the font_dim['height'] only for explicit 'y' scaling (not 'pa')
        target_height = self.font_dim['height']
        scale_ratio_y = target_height / sym_dim['height']

        if stretch == 'pa':
            # We want to preserve x/y aspect ratio, so find biggest scale
            # factor that allows symbol to fit
            scale_ratio_x = min(scale_ratio_x, scale_ratio_y)
            if not self.args.single:
                # non monospaced fonts just scale down on 'pa', not up
                scale_ratio_x = min(scale_ratio_x, 1.0)
            scale_ratio_y = scale_ratio_x
        else:
            # Keep the not-stretched direction
            if 'x' not in stretch:
                scale_ratio_x = 1.0
            if 'y' not in stretch:
                scale_ratio_y = 1.0

        return (scale_ratio_x, scale_ratio_y)

    def copy_glyphs(
        self,
        sourceFontStart,
        symbolFont,
        symbolFontStart,
        symbolFontEnd,
        exactEncoding,
        scaleRules,
        setName,
        attributes
    ):
        """ Copies symbol glyphs into self.sourceFont """
        progressText = ''
        careful = False
        glyphSetLength = 0
        sourceFontCounter = 0

        if self.args.careful:
            careful = True

        # Create glyphs from symbol font
        #
        # If we are going to copy all Glyphs, then assume we want to be careful
        # and only copy those that are not already contained in the source font
        if symbolFontStart == 0:
            symbolFont.selection.all()
            careful = True
        else:
            symbolFont.selection.select(
                (str("ranges"), str("unicode")),
                symbolFontStart,
                symbolFontEnd
            )

        # Get number of selected non-empty glyphs with codes >=0 (i.e. not -1
        # == notdef)
        symbolFontSelection = [
            x for x in symbolFont.selection.byGlyphs if x.unicode >= 0]
        glyphSetLength = len(symbolFontSelection)

        if not self.args.quiet:
            sys.stdout.write(
                "Adding " + str(
                    max(1, glyphSetLength)
                ) + " Glyphs from " + setName + " Set \n")

        currentSourceFontGlyph = -1  # initialize for the exactEncoding case
        width_warning = False

        for index, sym_glyph in enumerate(symbolFontSelection):
            index = max(1, index)

            sym_attr = attributes.get(sym_glyph.unicode)
            if sym_attr is None:
                sym_attr = attributes['default']

            if self.font_extrawide:
                # Do not allow 'xy2' scaling
                sym_attr['stretch'] = sym_attr['stretch'].replace('2', '')

            if exactEncoding:
                # Use the exact same hex values for the source font as for the
                # symbol font. Problem is we do not know the codepoint of the
                # sym_glyph and because it came from a selection.byGlyphs there
                # might be skipped over glyphs. The iteration is still in the
                # order of the selection by codepoint, so we take the next
                # allowed codepoint of the current glyph
                possible_codes = []
                if sym_glyph.unicode > currentSourceFontGlyph:
                    possible_codes += [sym_glyph.unicode]
                if sym_glyph.altuni:
                    possible_codes += [
                        v for v,
                        s,
                        r in sym_glyph.altuni if v > currentSourceFontGlyph
                    ]
                if len(possible_codes) == 0:
                    print(
                        "  Can not determine codepoint of {:X}. Skipping..."
                        .format(sym_glyph.unicode)
                    )
                    continue
                currentSourceFontGlyph = min(possible_codes)
            else:
                # use source font defined hex values based on passed in start
                # (fills gaps; symbols are packed)
                currentSourceFontGlyph = sourceFontStart + sourceFontCounter
                sourceFontCounter += 1

            # For debugging process only limited glyphs
            # if currentSourceFontGlyph != 0xe7bd:
            #     continue

            if not self.args.quiet:
                if self.args.progressbars:
                    update_progress(
                        round(float(index + 1) / glyphSetLength, 2))
                else:
                    progressText = "\nUpdating glyph: {} {} putting at: {:X}".format(
                        sym_glyph,
                        sym_glyph.glyphname,
                        currentSourceFontGlyph
                    )
                    sys.stdout.write(progressText)
                    sys.stdout.flush()

            # check if a glyph already exists in this location
            if careful or (
                'careful' in sym_attr['params']
            ) or (
                currentSourceFontGlyph in self.essential
            ):
                if currentSourceFontGlyph in self.sourceFont:
                    if not self.args.quiet:
                        careful_type = 'essential' if (
                            currentSourceFontGlyph in self.essential
                        ) else 'existing'
                        print("  Found {} Glyph at {:X}. Skipping...".format(
                            careful_type, currentSourceFontGlyph))
                    # We don't want to touch anything so move to next Glyph
                    continue
            else:
                # If we overwrite an existing glyph all subtable entries
                # regarding it will be wrong
                # (Probably; at least if we add a symbol and do not substitude
                # a ligature or such)
                if currentSourceFontGlyph in self.sourceFont:
                    self.sourceFont[currentSourceFontGlyph].removePosSub("*")

            # This will destroy any content currently in
        # currentSourceFontGlyph, so do it first
            glyph_scale_data = self.get_glyph_scale(
                sym_glyph.encoding,
                scaleRules,
                symbolFont,
                currentSourceFontGlyph
            ) if scaleRules is not None else None

            # Select and copy symbol from its encoding point
            # We need to do this select after the careful check, this way we
        # don't
            # reset our selection before starting the next loop
            symbolFont.selection.select(sym_glyph.encoding)
            symbolFont.copy()

            # Paste it
            self.sourceFont.selection.select(currentSourceFontGlyph)
            self.sourceFont.paste()
            self.sourceFont[currentSourceFontGlyph].glyphname = sym_glyph.glyphname
            # No autohints for symbols
            self.sourceFont[currentSourceFontGlyph].manualHints = True

            # Prepare symbol glyph dimensions
            sym_dim = get_glyph_dimensions(
                self.sourceFont[currentSourceFontGlyph])
            if glyph_scale_data is not None:
                if glyph_scale_data[1] is not None:
                    sym_dim = glyph_scale_data[1]  # Use combined bounding box
                # This is roughly alike get_scale_factors(glyph_scale_data[1],
            # 'pa')
                # Except we do not have glyph_scale_data[1] always...
                (scale_ratio_x, scale_ratio_y) = (
                    glyph_scale_data[0], glyph_scale_data[0])
            else:
                (scale_ratio_x, scale_ratio_y) = self.get_scale_factors(
                    sym_dim, sym_attr['stretch'])

            overlap = sym_attr['params'].get('overlap')
            if overlap:
                scale_ratio_x *= 1.0 + \
                    (self.font_dim['width'] /
                     (sym_dim['width'] * scale_ratio_x)) * overlap
                # never aggressive vertical overlap
                y_overlap = min(0.01, overlap)
                scale_ratio_y *= 1.0 + \
                    (self.font_dim['height'] /
                     (sym_dim['height'] * scale_ratio_y)) * y_overlap

            # Size in x to size in y ratio limit (to prevent over-wide glyphs)
            xy_ratio_max = sym_attr['params'].get('xy-ratio')
            if (xy_ratio_max):
                xy_ratio = sym_dim['width'] * scale_ratio_x / \
                    (sym_dim['height'] * scale_ratio_y)
                if xy_ratio > xy_ratio_max:
                    scale_ratio_x = scale_ratio_x * xy_ratio_max / xy_ratio

            if scale_ratio_x != 1.0 or scale_ratio_y != 1.0:
                self.sourceFont[currentSourceFontGlyph].transform(
                    psMat.scale(scale_ratio_x, scale_ratio_y))

            # We pasted and scaled now we want to align/move
            # Use the dimensions from the newly pasted and stretched glyph to
        # avoid any rounding errors
            sym_dim = get_glyph_dimensions(
                self.sourceFont[currentSourceFontGlyph])
            # Use combined bounding box?
            if (
                glyph_scale_data is not None
            ) and (
                glyph_scale_data[1] is not None
            ):
                scaleglyph_dim = scale_bounding_box(
                    glyph_scale_data[1], scale_ratio_x, scale_ratio_y)
                if scaleglyph_dim['advance'] is None:
                    # On monospaced symbol collections use their advance with,
                    # otherwise align horizontally individually
                    scaleglyph_dim['xmin'] = sym_dim['xmin']
                    scaleglyph_dim['xmax'] = sym_dim['xmax']
                    scaleglyph_dim['width'] = sym_dim['width']
                sym_dim = scaleglyph_dim

            y_align_distance = 0
            if sym_attr['valign'] == 'c':
                # Center the symbol vertically by matching the center of the
                # line height and center of symbol
                sym_ycenter = sym_dim['ymax'] - (sym_dim['height'] / 2)
                font_ycenter = self.font_dim['ymax'] - \
                    (self.font_dim['height'] / 2)
                y_align_distance = font_ycenter - sym_ycenter

            # Handle glyph l/r/c alignment
            x_align_distance = 0
            if self.args.nonmono and sym_dim['advance'] is None:
                # Remove left side bearing
                # (i.e. do not remove left side bearing when combined BB is in
                # use)
                x_align_distance = - \
                    self.sourceFont[currentSourceFontGlyph].left_side_bearing
            elif sym_attr['align']:
                # First find the baseline x-alignment (left alignment amount)
                x_align_distance = self.font_dim['xmin'] - sym_dim['xmin']
                if sym_attr['align'] == 'c':
                    # Center align
                    x_align_distance += (self.font_dim['width'] /
                                         2) - (sym_dim['width'] / 2)
                elif sym_attr['align'] == 'r':
                    # Right align
                    x_align_distance += self.font_dim['width'] - \
                        sym_dim['width']
                    if not self.args.single and '2' in sym_attr['stretch']:
                        x_align_distance += self.font_dim['width']

            if overlap:
                overlap_width = self.font_dim['width'] * overlap
                if sym_attr['align'] == 'l':
                    x_align_distance -= overlap_width
                if sym_attr['align'] == 'r' and not self.args.nonmono:
                    # Nonmono is 'left aligned' per definition, translation
                    # does not help here
                    x_align_distance += overlap_width

            align_matrix = psMat.translate(x_align_distance, y_align_distance)
            self.sourceFont[currentSourceFontGlyph].transform(align_matrix)

            # Ensure after horizontal adjustments and centering that the glyph
            # does not overlap the bearings (edges)
            if not overlap:
                self.remove_glyph_neg_bearings(
                    self.sourceFont[currentSourceFontGlyph])

            # Needed for setting 'advance width' on each glyph so they do not
            # overlap, also ensures the font is considered monospaced on
            # Windows by setting the same width for all character glyphs. This
            # needs to be done for all glyphs, even the ones that are empty and
            # didn't go through the scaling operations. It should come after
            # setting the glyph bearings
            if not self.args.nonmono:
                self.set_glyph_width_mono(
                    self.sourceFont[currentSourceFontGlyph])
            else:
                # Target font with variable advance width get the icons with
                # their native widths and keeping possible (right and/or
                # negative) bearings in effect
                if sym_dim['advance'] is not None:
                    # 'Width' from monospaced scale group
                    width = sym_dim['advance']
                else:
                    width = sym_dim['width']
                # If we have overlap we need to subtract that to keep/get
                # negative bearings
                if overlap and (
                    sym_attr['align'] == 'l' or sym_attr['align'] == 'r'
                ):
                    width -= overlap_width
                # Fontforge handles the width change like this:
                # - Keep existing left_side_bearing
                # - Set width
                # - Calculate and set new right_side_bearing
                self.sourceFont[currentSourceFontGlyph].width = int(width)

            # Check if the inserted glyph is scaled correctly for monospace
            if self.args.single:
                (xmin, _, xmax,
                 _) = self.sourceFont[currentSourceFontGlyph].boundingBox()
                if (
                    int(xmax - xmin) >
                    self.font_dim['width'] * (1 + (overlap or 0))
                ):
                    print(
                        "\n  Warning: Scaled glyph U+{:X} wider than one"
                        " monospace width ({} / {} (overlap {}))"
                        .format(
                            currentSourceFontGlyph,
                            int(xmax - xmin),
                            self.font_dim['width'],
                            overlap
                        )
                    )

        # end for

        if not self.args.quiet:
            sys.stdout.write("\n")

    def set_sourcefont_glyph_widths(self):
        """ Makes self.sourceFont monospace compliant """

        for glyph in self.sourceFont.glyphs():
            if (glyph.width == self.font_dim['width']):
                # Don't touch the (negative) bearings if the width is ok
                # Ligartures will have these.
                continue

            if (glyph.width != 0):
                # If the width is zero this glyph is intened to be printed on
                # top of another one. In this case we need to keep the negative
                # bearings to shift it 'left'. Things like &Auml; have these:
                # composed of U+0041 'A' and U+0308 'double dot above'
                #
                # If width is not zero, correct the bearings such that they are
                # within the width:
                self.remove_glyph_neg_bearings(glyph)

            self.set_glyph_width_mono(glyph)

    def remove_glyph_neg_bearings(self, glyph):
        """ Sets passed glyph's bearings 0 if they are negative. """
        try:
            if glyph.left_side_bearing < 0:
                glyph.left_side_bearing = 0
            if glyph.right_side_bearing < 0:
                glyph.right_side_bearing = 0
        except:
            pass

    def set_glyph_width_mono(self, glyph):
        """ Sets passed glyph.width to self.font_dim.width.

        self.font_dim.width is set with self.get_sourcefont_dimensions().
        """
        try:
            # Fontforge handles the width change like this:
            # - Keep existing left_side_bearing
            # - Set width
            # - Calculate and set new right_side_bearing
            glyph.width = self.font_dim['width']
        except:
            pass

    def prepareScaleRules(self, scaleRules, symbolFont, destGlyph):
        """ Prepare raw ScaleRules data for use """
        # The scaleRules is/will be a dict with these (possible) entries:
        # 'ScaleGroups': List of ((lists of glyph codes) or (ranges of glyph
        # codes)) that shall be scaled
        # 'scales': List of associated scale factors, one for each entry in
        # 'ScaleGroups' (generated by this function)
        # 'bbdims': List of associated sym_dim dicts, one for each entry in
        # 'ScaleGroups' (generated by this function). Each dim_dict describes
        # the combined bounding box of all glyphs in one ScaleGroups group
        # Example:
        # { 'ScaleGroups': [ range(1, 3), [ 7, 10 ], ],
        #   'scales':      [ 1.23,        1.33,      ],
        #   'bbdims':      [ dim_dict1,   dim_dict2, ] }
        #
        # Each item in 'ScaleGroups' (a range or an explicit list) forms a
        # group of glyphs that shall be as rescaled all with the same and
        # maximum possible (for the included glyphs) 'pa' factor.
        # If the 'bbdims' is present they all shall be shifted in the same way.
        #
        # Previously this structure has been used:
        #   'ScaleGlyph' Lead glyph, which scaling factor is taken
        #   'GlyphsToScale': List of ((glyph code) or (tuple of two glyph codes
        #   that form a closed range)) that shall be scaled
        #   Note that this allows only one group for the whle symbol font, and
        #   that the scaling factor is defined by a specific character, which
        #   needs to be manually selected (on each symbol font update).
        #   Previous entries are automatically rewritten to the new style.
        #
        # Note that scaleRules is overwritten with the added data.
        if 'scales' in scaleRules:
            # Already prepared... must not happen, ignore call
            return

        scaleRules['scales'] = []
        scaleRules['bbdims'] = []
        if 'ScaleGroups' not in scaleRules:
            scaleRules['ScaleGroups'] = []
        for group in scaleRules['ScaleGroups']:
            sym_dim = get_multiglyph_boundingBox(
                [symbolFont[g] if g in symbolFont else None for g in group],
                destGlyph
            )
            scale = self.get_scale_factors(sym_dim, 'pa')[0]
            scaleRules['scales'].append(scale)
            scaleRules['bbdims'].append(sym_dim)

        if 'ScaleGlyph' in scaleRules:
            # Rewrite to equivalent ScaleGroup
            group_list = []
            if 'GlyphsToScale+' in scaleRules:
                key = 'GlyphsToScale+'
                plus = True
            else:
                key = 'GlyphsToScale'
                plus = False
            for i in scaleRules[key]:
                if isinstance(i, tuple):
                    group_list.append(range(i[0], i[1] + 1))
                else:
                    group_list.append(i)
            sym_dim = get_glyph_dimensions(
                symbolFont[scaleRules['ScaleGlyph']])
            scale = self.get_scale_factors(sym_dim, 'pa')[0]
            scaleRules['ScaleGroups'].append(group_list)
            scaleRules['scales'].append(scale)
            if plus:
                scaleRules['bbdims'].append(sym_dim)
            else:
                # The 'old' style keeps just the scale, not the positioning
                scaleRules['bbdims'].append(None)

    def get_glyph_scale(
        self,
        symbol_unicode,
        scaleRules,
        symbolFont,
        dest_unicode
    ):
        """ Determines whether or not to use scaled glyphs for glyph in passed
        symbol_unicode """
        # Potentially destorys the contents of self.sourceFont[dest_unicode]
        if 'scales' not in scaleRules:
            if dest_unicode not in self.sourceFont:
                self.sourceFont.createChar(dest_unicode)
            self.prepareScaleRules(
                scaleRules, symbolFont, self.sourceFont[dest_unicode])
        for glyph_list, scale, box in zip(
            scaleRules['ScaleGroups'],
            scaleRules['scales'],
            scaleRules['bbdims']
        ):
            for e in glyph_list:
                if isinstance(e, range):
                    if symbol_unicode in e:
                        return (scale, box)
                elif symbol_unicode == e:
                    return (scale, box)
        return None


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
            "{}: You seem to be using an unsupported (old)"
            " version of fontforge: {}\n"
            .format(
                projectName, actualVersion
            )
        )
        sys.stderr.write("{}: Please use at least version: {}\n".format(
            projectName, minimumVersion))
        sys.exit(1)


def setup_arguments():
    parser = argparse.ArgumentParser(
        description=(
            'Nerd Fonts Font Patcher: patches a given font with programming'
            ' and development related glyphs\n\n'
            '* Website: https://www.nerdfonts.com\n'
            '* Version: ' + version + '\n'
            '* Development Website: https://github.com/ryanoasis/nerd-fonts\n'
            '* Changelog:'
            'https://github.com/ryanoasis/nerd-fonts/blob/-/changelog.md'),
        formatter_class=RawTextHelpFormatter
    )

    # optional arguments
    parser.add_argument(
        'font',
        help='The path to the font to patch (e.g., Inconsolata.otf)'
    )
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=projectName + ": %(prog)s (" + version + ")"
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
        '-q',
        '--quiet',
        '--shutup',
        dest='quiet',

        default=False,
        action='store_true',
        help='Do not generate verbose output'
    )
    parser.add_argument(
        '-w',
        '--windows',
        dest='windows',
        default=False,
        action='store_true',
        help='Limit the internal font name to 31 characters'
             ' (for Windows compatibility)'
    )
    parser.add_argument(
        '-c',
        '--complete',
        dest='complete',
        default=False,
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
        '--removeligs',
        '--removeligatures',
        dest='removeligatures',
        default=False,
        action='store_true',
        help='Removes ligatures specificed in JSON configuration file'
    )
    parser.add_argument(
        '--postprocess',
        dest='postprocess',
        default=False,
        type=str,
        nargs='?',
        help='Specify a Script for Post Processing'
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
        '--custom',
        dest='custom',
        default=False,
        type=str,
        nargs='?',
        help='Specify a custom symbol font. All new glyphs will'
             ' be copied, with no scaling applied.'
    )
    parser.add_argument(
        '-ext',
        '--extension',
        dest='extension',

        default="",
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
        '--makegroups',
        dest='makegroups',
        default=False,
        action='store_true',
        help='Use alternative method to name patched fonts(experimental)'
    )
    parser.add_argument(
        '--variable-width-glyphs',
        dest='nonmono',
        default=False,
        action='store_true',
        help='Do not adjust advance width(no "overhang")'
    )

    # progress bar arguments
    # https://stackoverflow.com/questions/15008758/parsing-boolean-values-with-argparse
    progressbars_group_parser = parser.add_mutually_exclusive_group(
        required=False
    )
    progressbars_group_parser.add_argument(
        '--progressbars',
        dest='progressbars',
        action='store_true',
        help='Show percentage completion progress bars per Glyph Set'
    )
    progressbars_group_parser.add_argument(
        '--no-progressbars',
        dest='progressbars',
        action='store_false',
        help='Don\'t show percentage completion progress bars per Glyph Set'
    )
    parser.set_defaults(progressbars=True)
    parser.add_argument(
        '--also-windows',
        dest='alsowindows',
        default=False,
        action='store_true',
        help='Create two fonts, the normal and the --windows version'
    )

    # symbol fonts to include arguments
    sym_font_group = parser.add_argument_group('Symbol Fonts')
    sym_font_group.add_argument(
        '--fontawesome',
        dest='fontawesome',
        default=False,
        action='store_true',
        help='Add Font Awesome Glyphs (http://fontawesome.io/)'
    )
    sym_font_group.add_argument(
        '--fontawesomeextension',
        dest='fontawesomeextension',
        default=False,
        action='store_true',
        help='Add Font Awesome Extension Glyphs'
             ' (https://andrelzgava.github.io/font-awesome-extension/)'
    )
    sym_font_group.add_argument(
        '--fontlogos',
        '--fontlinux',
        dest='fontlogos',
        default=False,
        action='store_true',
        help='Add Font Logos Glyphs (https://github.com/Lukas-W/font-logos)'
    )
    sym_font_group.add_argument(
        '--octicons',
        dest='octicons',
        default=False,
        action='store_true',
        help='Add Octicons Glyphs (https://octicons.github.com)'
    )
    sym_font_group.add_argument(
        '--codicons',
        dest='codicons',
        default=False,
        action='store_true',
        help='Add Codicons Glyphs'
             ' (https://github.com/microsoft/vscode-codicons)'
    )
    sym_font_group.add_argument(
        '--powersymbols',
        dest='powersymbols',
        default=False,
        action='store_true',
        help='Add IEC Power Symbols (https://unicodepowersymbol.com/)'
    )
    sym_font_group.add_argument(
        '--pomicons',
        dest='pomicons',
        default=False,
        action='store_true',
        help='Add Pomicon Glyphs (https://github.com/gabrielelana/pomicons)'
    )
    sym_font_group.add_argument(
        '--powerline',
        dest='powerline',
        default=False,
        action='store_true',
        help='Add Powerline Glyphs'
    )
    sym_font_group.add_argument(
        '--powerlineextra',
        dest='powerlineextra',
        default=False,
        action='store_true',
        help='Add Powerline Glyphs'
             ' (https://github.com/ryanoasis/powerline-extra-symbols)'
    )
    sym_font_group.add_argument(
        '--material',
        '--materialdesignicons',
        '--mdi',
        dest='material',
        default=False,
        action='store_true',
        help='Add Material Design Icons'
             ' (https://github.com/templarian/MaterialDesign)'
    )
    sym_font_group.add_argument(
        '--weather',
        '--weathericons',
        dest='weather',
        default=False,
        action='store_true',
        help='Add Weather Icons (https://github.com/erikflowers/weather-icons)'
    )

    args = parser.parse_args()

    if args.makegroups and not FontnameParserOK:
        sys.exit(
            "{}: FontnameParser module missing"
            " (bin/scripts/name_parser/Fontname*),"
            " can not --makegroups"
            .format(projectName)
        )

    # if you add a new font, set it to True here inside the if condition
    if args.complete:
        args.fontawesome = True
        args.fontawesomeextension = True
        args.fontlogos = True
        args.octicons = True
        args.codicons = True
        args.powersymbols = True
        args.pomicons = True
        args.powerline = True
        args.powerlineextra = True
        args.material = True
        args.weather = True

    if not args.complete:
        sym_font_args = []
        # add the list of arguments for each symbol font to the list
        # sym_font_args
        for action in sym_font_group._group_actions:
            sym_font_args.append(action.__dict__['option_strings'])

        # determine whether or not all symbol fonts are to be used
        font_complete = True
        for sym_font_arg_aliases in sym_font_args:
            found = False
            for alias in sym_font_arg_aliases:
                if alias in sys.argv:
                    found = True
            if not found:
                font_complete = False
        args.complete = font_complete

    if args.alsowindows:
        args.windows = False

    if args.nonmono and args.single:
        print(
            "Warning: Specified contradicting --variable-width-glyphs and"
            " --use-single-width-glyph. Ignoring --variable-width-glyphs."
        )
        args.nonmono = False

    make_sure_path_exists(args.outputdir)
    if not os.path.isfile(args.font):
        sys.exit("{}: Font file does not exist: {}".format(
            projectName, args.font))
    if not os.access(args.font, os.R_OK):
        sys.exit("{}: Can not open font file for reading: {}".format(
            projectName, args.font))
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
    except:
        args.is_variable = False
    finally:
        try:
            source_font_test.close()
        except:
            pass

    if args.extension == "":
        args.extension = os.path.splitext(args.font)[1]
    else:
        args.extension = '.' + args.extension
    if re.match("\.ttc$", args.extension, re.IGNORECASE):
        if not is_ttc:
            sys.exit(
                projectName
                + ": Can not create True Type Collections"
                + " from single font files"
            )
    else:
        if is_ttc:
            sys.exit(
                projectName
                + ": Can not create single font files"
                " from True Type Collections")

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
            # 1 = ("fstypepermitted",))
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