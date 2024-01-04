import sys
import argparse

try:
    import fontforge
except ImportError:
    sys.exit("fontforge not installed!")

# arguments
parser = argparse.ArgumentParser(
    prog="font-rename",
    description="rename font name fields using fontforge",
)

parser.add_argument(
    "font",
    nargs=1,
    help="relative path to font file"
)
parser.add_argument(
    "-w", "--weight",
    default="regular",
    help="weight of font, used in naming",
    type=str,
)
parser.add_argument(
    "-n", "--name",
    help="common name/prefix to use for all name fields",
    type=str,
)
parser.add_argument(
    "--fontname",
    help="specify PostScript font name",
    type=str,
)
parser.add_argument(
    "--familyname",
    help="specify PostScript font family name",
    type=str,
)
parser.add_argument(
    "--fullname",
    help="specify PostScript font name",
    type=str,
)

args = parser.parse_args()

new_fontname = args.fontname
new_fullname = args.fullname
new_familyname = args.familyname

try:
    font = fontforge.open(args.font[0])
except Exception as e:
    print("Exception:", e)
    sys.exit(
        "ERROR: could not open file in fontforge!"
        + " Please check ./%s exists and is a valid font file..."
        % args.font[0]
    )

# get original name fields
original_fontname = font.fontname
original_fullname = font.fullname
original_familyname = font.familyname

if args.name is not None:
    print("name override provided, using", args.name, "as name/prefix...")
    new_fontname = args.name + "-" + args.weight
    new_fullname = args.name + "-" + args.weight
    new_familyname = args.name

print("  fontname:", original_fontname, "-->", new_fontname)
print("  fullname:", original_fullname, "-->", new_fullname)
print("  familyname:", original_familyname, "-->", new_familyname)

font.fontname = new_fontname
font.fullname = new_fullname
font.familyname = new_familyname

# clear comment and log fields
font.comment = ""
font.fontlog = ""

# add new sfnt names
font.appendSFNTName("English (US)", "Family", new_familyname)
font.appendSFNTName("English (US)", "SubFamily", args.weight)
font.appendSFNTName("English (US)", "UniqueID", new_fontname)
font.appendSFNTName("English (US)", "Fullname", new_fullname)
font.appendSFNTName("English (US)", "PostScriptName", new_fontname)
font.appendSFNTName("English (US)", "Preferred Family", new_familyname)
font.appendSFNTName("English (US)", "Compatible Full", new_fullname)

ligature_name = 'f_l'
ligature_tuple = ('f', 'l')
font.addLookup(
    'ligatures',
    'gsub_ligature',
    (),
    [['rlig', [['arab', ['dflt']]]]]
)
font.addLookupSubtable('ligatures', 'ligatureshi')
glyph = font.createChar(-1, ligature_name)
glyph.addPosSub('ligatureshi', ligature_tuple)

flags = (
    str("opentype"),
    str("no-FFTM-table"),
)

filename = new_fontname + ".otf"
print("generating new font file", filename)
font.generate(filename, flags=flags)
