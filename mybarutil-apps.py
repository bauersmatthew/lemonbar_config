#!/usr/bin/env python
import sys

SPACING="          "
SPACING_HALF="     "

#sys.stdout = codecs.getwriter('utf8')(sys.stdout)

infolines = sys.argv[1].split(';;')[1:]
#print(sys.argv[1])
infosplits = [l.split('|') for l in infolines]
#print(len(infolines))
infosplits.sort(key=lambda x: x[0]) # sort by ID first
infosplits.sort(key=lambda x: x[1]) # then by class

icon_table = {
    'Lilyterm' : '\uf120',
    'URxvt' : '\uf120',
    'Firefox' : '\uf269',
    'Emacs' : '\uf121'
}

total_out = SPACING
for wininfo in infosplits:
    winid = wininfo[0]
    winclass = wininfo[1]
    char = winclass[0]
    if winclass in icon_table:
        char = icon_table[winclass]
    else:
        sys.stderr.write(char)
    active = (winid == sys.argv[2])
    out  = '%{{A1:xdotool windowactivate {id}:}}'.format(id=winid)
    out += '%{{A3:xdotool windowminimize {id}:}}'.format(id=winid)
    out += SPACING_HALF
    out += '{c}{sh}%{{A}}%{{A}}'.format(c=char, sh=SPACING_HALF)
    if active:
        out = '%{{R}}{}%{{R}}'.format(out)
    total_out += out

sys.stdout.write(total_out)
