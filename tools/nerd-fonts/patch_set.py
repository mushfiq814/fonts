def setup_patch_set():
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
    return [
        {
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
            'Name': "Codicons",
            'Filename': "codicons/codicon.ttf",
            'Exact': True,
            'SymStart': 0xEA60,
            'SymEnd': 0xEBEB,
            'SrcStart': None,
            'ScaleRules': None,
            'Attributes': SYM_ATTR_DEFAULT
        },
    ]
