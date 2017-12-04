#!/usr/bin/python
import sys
import subprocess
import codecs

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

# get info from amixer
volume_info = subprocess.check_output(
    'amixer -D pulse get Master | grep "Front Left:"',
    shell=True).strip().split()
percent = int(volume_info[4][1:-2])
status = 'on' in volume_info[5]

# construct output
if not status:
    sys.stdout.write(u'\uf026')
else:
    if percent < 50:
        sys.stdout.write(u'\uf027')
    else:
        sys.stdout.write(u'\uf028')
    sys.stdout.write(' (' + str(percent) + '%)')
