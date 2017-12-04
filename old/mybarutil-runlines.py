#!/usr/bin/env python

import sys
import subprocess

for line in sys.stdin:
    subprocess.run(line, shell=True)
