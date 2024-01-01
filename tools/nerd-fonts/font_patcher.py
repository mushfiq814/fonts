from __future__ import absolute_import, print_function, unicode_literals
import sys
import re
import os

import TableHEADWriter
from patch_set import setup_patch_set
from utils import (
    check_panose_monospaced,
    panose_check_to_text,
    is_monospaced,
    report_advance_widths,
    half_gap,
    sanitize_filename,
    get_glyph_dimensions,
    update_progress,
    get_multiglyph_boundingBox,
    scale_bounding_box,
)

try:
    import configparser
except ImportError:
    sys.exit("configparser not found!")
try:
    import psMat
    import fontforge
except ImportError:
    sys.exit("fontforge not found!")


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
        self.get_essential_references()
        self.setup_name_backup(font)
        if self.args.single:
            self.assert_monospace()
        patch_set = setup_patch_set()
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
                "Can not find symbol glyph directory {} "
                "(probably you need to download the src/glyphs/ directory?)"
                .format(self.args.glyphdir)
            )

        for patch in patch_set:
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
                        "Can not find symbol source for"
                        "'{}'\n{}  (i.e. {})"
                        .format(
                            patch['Name'],
                            '',
                            self.args.glyphdir + patch['Filename']
                        )
                    )
                if not os.access(
                    self.args.glyphdir + patch['Filename'],
                    os.R_OK
                ):
                    sys.exit(
                        " Can not open symbol source for '{}'\n{} "
                        " (i.e. {})"
                        .format(
                            patch['Name'],
                            '',
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
        gen_flags = (str('opentype'), str('no-FFTM-table'))
        if len(sourceFonts) > 1:
            layer = None
            # use first non-background layer
            for layer in sourceFont.layers:
                if not sourceFont.layers[layer].is_background:
                    layer = layer
                    break
            outfile = os.path.normpath(os.path.join(
                sanitize_filename(self.args.outputdir, True),
                sanitize_filename(sourceFont.familyname) + ".ttc"))
            sourceFonts[0].generateTtc(
                outfile, sourceFonts[1:], flags=gen_flags, layer=layer)
            message = "   Generated {} fonts\n   ===> '{}'".format(
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
                print("Preserving bitmaps %s" % self.sourceFont.bitmapSizes)
                bitmaps = str('otf')  # otf/ttf, both is bf_ttf
            sourceFont.generate(outfile, bitmap_type=bitmaps, flags=gen_flags)
            message = "   %s\n   ===> '%s'" % (
                self.sourceFont.fullname,
                outfile
            )

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
                    print("Tweaking {}/{}".format(
                        idx + 1, source_font.num_fonts
                    ))
                    source_font.find_head_table(idx)
                    dest_font.find_head_table(idx)
                    if (
                        (
                            source_font.flags & 0x08 == 0
                        ) and (
                            dest_font.flags & 0x08 != 0
                        )
                    ):
                        print(
                            "Changing flags from 0x{:X} to 0x{:X}"
                            .format(
                                dest_font.flags, dest_font.flags & ~0x08
                            )
                        )
                        # clear 'ppem_to_int'
                        dest_font.putshort(dest_font.flags & ~0x08, 'flags')
                    if source_font.lowppem != dest_font.lowppem:
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
                except Exception:
                    pass
        if self.args.is_variable:
            print(
                "Warning: Source font is a variable open type font (VF)"
                " and the patch results will most likely not be what you want"
            )
        print(message)

    def setup_name_backup(self, font):
        """ Store the original font names to be able to rename the font
        multiple times """
        font.persistent = {
            "fontname": font.fontname,
            "fullname": font.fullname,
            "familyname": font.familyname,
        }

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
                    ": Font will not be patched! Give --mono (or -s, or"
                    " --use-single-width-glyphs) twice to force patching"
                )

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
                "WARNING Font vertical metrics inconsistent"
                " (HHEA {} / TYPO {} / WIN {}), using WIN"
                .format(hhea_btb, typo_btb, win_btb)
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
            sys.exit("Can not detect sane font height")

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
        # Do not warn if proportional target
        warned = self.args.nonmono
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

    # TODO: simplify this
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

        sys.stdout.write(
            "Adding " + str(
                max(1, glyphSetLength)
            ) + " Glyphs from " + setName + " Set \n")

        currentSourceFontGlyph = -1  # initialize for the exactEncoding case

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

            if self.args.progressbars:
                update_progress(
                    round(float(index + 1) / glyphSetLength, 2))
            else:
                progressText = (
                    "\nUpdating glyph:",
                    " {} {} putting at: {:X}"
                ).format(
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
            # don't reset our selection before starting the next loop
            symbolFont.selection.select(sym_glyph.encoding)
            symbolFont.copy()

            # Paste it
            self.sourceFont.selection.select(currentSourceFontGlyph)
            self.sourceFont.paste()
            self.sourceFont[currentSourceFontGlyph].glyphname = \
                sym_glyph.glyphname
            # No autohints for symbols
            self.sourceFont[currentSourceFontGlyph].manualHints = True

            # Prepare symbol glyph dimensions
            sym_dim = get_glyph_dimensions(
                self.sourceFont[currentSourceFontGlyph])
            if glyph_scale_data is not None:
                if glyph_scale_data[1] is not None:
                    sym_dim = glyph_scale_data[1]  # Use combined bounding box
                # This is roughly alike get_scale_factors(glyph_scale_data[1],
                # 'pa') Except we do not have glyph_scale_data[1] always...
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
        except Exception:
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
        except Exception:
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
