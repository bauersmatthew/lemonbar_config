#!/usr/bin/python
import sys
import subprocess
import codecs

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

# get max brightness
bright_max = None
with open('/sys/class/backlight/intel_backlight/max_brightness') as fin:
    bright_max = int(fin.read().strip())

# get current brightness
bright_curr = None
with open('/sys/class/backlight/intel_backlight/brightness') as fin:
    bright_curr = int(fin.read().strip())

bright_percent = 100.0*float(bright_curr)/float(bright_max)
if bright_percent >= 98.0:
    bright_percent = 100.0

# choose icon
if bright_percent < 33.3:
    sys.stdout.write(u'\uf006')
elif bright_percent < 66.6:
    sys.stdout.write(u'\uf123')
else:
    sys.stdout.write(u'\uf005')
