#!/usr/bin/python
import sys
import subprocess
import codecs

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

# get info from acpi
battery_info = subprocess.check_output(('acpi', '-b'))
charging = ('Discharging' not in battery_info)
if 'Full' in battery_info:
    percent = 100
else:
    percent = int(battery_info.split()[3][:-2])

# construct output
output = u''
if charging:
    output += u'\uf1e6 '
if percent < 25:
    output += u'\uf244 (' + str(percent) + u'%)'
elif percent < 50:
    output += u'\uf243'
elif percent < 75:
    output += u'\uf242'
elif percent < 95:
    output += u'\uf241'
else:
    output += u'\uf240'

sys.stdout.write(output)
