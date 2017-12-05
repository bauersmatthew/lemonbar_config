#!/usr/bin/env python
from subprocess import Popen, PIPE
from datetime import datetime
import threading
import time

SPACING="          "
SPACING_HALF="     "

class Renderer:
    """Base class for all bar renderers."""
    def __init__(self, fun):
        self.fun = fun
        self.cached = None

    def update(self):
        """Will update the cached value."""
        self.cached = self.fun()

    def render(self):
        """Will get a cached value if available."""
        if self.cached is None:
            self.update()
        return self.cached

renderers = {}
def register(name):
    def wrap(fun):
        renderers[name] = Renderer(fun)
        return fun
    return wrap

def render(name):
    return renderers[name].render()
def update(name):
    renderers[name].update()

def get_real_windows():
    """Get dictionary of normal window IDS -> window classes."""
    real_windows = {} # id -> class
    with Popen('wmctrl -xl'.split(), stdout=PIPE, stderr=PIPE) as proc:
        for line in proc.stdout:
            fields = line.split()
            winid = str(int(fields[0].decode('utf8').strip(), 16))
            winclass = fields[2].decode('utf8').split('.')[1]
            if fields[1].decode('utf8') != '-1': # not a bar
                real_windows[winid] = winclass
    return real_windows

@register('apps')
def render_apps():
    """Render the taskbar-like section of the bar."""
    windows = get_real_windows()
    windows_sorted = sorted(sorted(windows.items(), key=lambda x: x[0]),
                            key=lambda x: x[1])
    active_winid = None
    with Popen('xdotool getactivewindow'.split(),
               stdout=PIPE, stderr=PIPE) as xdt_proc:
        out = xdt_proc.stdout.read().decode('utf8').strip()
        if out:
            active_winid = out
    icon_table = {
        'Lilyterm' : '\uf120',
        'URxvt' : '\uf120',
        'Firefox' : '\uf269',
        'Emacs' : '\uf121'
    }
    total_out = SPACING_HALF
    for winid, winclass in windows_sorted:
        icon = winclass[0] # use first letter by default
        if winclass in icon_table:
            icon = icon_table[winclass]
        out  = '%{{A1:xdotool windowactivate {id}:}}'.format(id=winid)
        out += '%{{A3:xdotool windowminimize {id}:}}'.format(id=winid)
        out += SPACING_HALF
        out += '{c}{sh}%{{A}}%{{A}}'.format(c=icon, sh=SPACING_HALF)
        if winid == active_winid:
            out = '%{{R}}{}%{{R}}'.format(out)
        total_out += out
    return total_out

@register('clock')
def render_clock():
    """Render the time."""
    return datetime.now().strftime('%l:%M').strip()

@register('battery')
def render_battery():
    """Render the battery level."""
    warning = False
    charging = True
    percent = None
    with Popen('acpi -b'.split(), stdout=PIPE) as proc:
        out = proc.stdout.read().decode('utf8').strip()
        if 'Discharging' in out:
            charging = False
        if 'Full' in out:
            percent = 100
        else:
            percent = int(out.split()[3][:2])
    out = ''
    if charging:
        out += '\uf1e6 ' # power cord
    if percent < 25:
        out += '\uf244 ({}%)'.format(percent) # 0/4 battery
    elif percent < 50:
        out += '\uf243' # 1/4 battery
    elif percent < 75:
        out += '\uf242' # 2/4 battery
    elif percent < 95:
        out += '\uf241' # 3/4 battery
    else:
        out += '\uf240' # 4/4 battery
    return out

@register('brightness')
def render_brightness():
    """Render the screen brightness."""
    bright_max = None
    with open('/sys/class/backlight/intel_backlight/max_brightness') as fin:
        bright_max = int(fin.read().strip())
    bright_now = None
    with open('/sys/class/backlight/intel_backlight/brightness') as fin:
        bright_now = int(fin.read().strip())
    bright_percent = 100*bright_now/bright_max
    if bright_percent < 33.3:
        return '\uf006' # empty star
    elif bright_percent < 66.6:
        return '\uf123' # half-full star
    return '\uf005' # full star

@register('volume')
def render_volume():
    """Render the volume level."""
    info_all = None
    with Popen('amixer -D pulse get Master'.split(), stdout=PIPE) as proc:
        info_all = proc.stdout.read().decode('utf8').strip().split('\n')
    info = None
    for line in info_all:
        if 'Front Left:' in line:
            info = line.strip().split()
            break
    percent = int(info[4][1:-2])
    status = 'on' in info[4]
    if not status or percent == 0:
        return '\uf026' # muted
    if percent < 50:
        return '\uf027' # low speaker
    return '\uf028' # high speaker

@register('network')
def render_network():
    """Render the network connectivity status."""
    status = None
    with Popen('/usr/sbin/iw wlp2s0 link'.split(), stdout=PIPE) as proc:
        status = proc.stdout.read().decode('utf8').strip()
    if status == 'Not connected.':
        return '\uf127' # broken chain
    return '\uf1eb' # wifi

def render_all():
    """Render the entire bar."""
    return (
        '%{{l}}{s}{apps}'
        '%{{c}}{clock}%'
        '{{r}}{network}{s}{volume}{s}{brightness}{s}{battery}{s}\n'
    ).format(s=SPACING,
             apps=render('apps'),
             clock=render('clock'),
             network=render('network'),
             volume=render('volume'),
             brightness=render('brightness'),
             battery=render('battery'))

def update_bar(bar_process):
    """Re-render and update the bar."""
    bar_process.stdin.write(render_all())

class HeartbeatThread(threading.Thread):
    """The thread that updates the bar automatically on an interval."""
    def __init__(self, bar_process):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.bar = bar_process
        self.stop = False

    def update_all(self):
        for name in renderers:
            update(name)

    def run(self):
        while not self.stop:
            self.update_all()
            update_bar(self.bar)
            time.sleep(2) # sleep for .5 seconds

    def stop(self):
        self.stop = True

def main():
    """Main routine."""
    # open lemonbar
    lemonbar_cmd = ('lemonbar '
                    '-o 0 -f noto:size=22 -o -2 -f fontawesome:size=22 '
                    '-B #ff2a2a2a -F #ffeeeeee '
                    '-g 3200x50')
    with Popen(lemonbar_cmd.split(), stdout=PIPE, stdin=PIPE,
               bufsize=1, universal_newlines=True) as proc:
        heartbeat = HeartbeatThread(proc)
        heartbeat.start()
        for line in proc.stdout:
            # each line is a command to run
            Popen(line.strip(), shell=True).wait()
            update('apps')
            update_bar(proc)
        heartbeat.stop()

if __name__ == '__main__':
    main()
