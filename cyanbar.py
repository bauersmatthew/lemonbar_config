#!/usr/bin/env python
from subprocess import Popen, PIPE
import subprocess
from datetime import datetime
import threading
import time
import argparse
import fcntl
import os
import os.path
import sys
import signal
import evdev
import string

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
hidden = {}
def register(name):
    def wrap(fun):
        renderers[name] = Renderer(fun)
        return fun
    return wrap

def render(name):
    if name not in hidden:
        return renderers[name].render()
    return ''
def update(name):
    renderers[name].update()
def hide(name):
    global hidden
    hidden[name] = True
def unhide(name):
    global hidden
    if name in hidden:
        del hidden[name]

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
    percent = None
    charging = None
    with open('/sys/class/power_supply/BAT1/capacity') as fin:
        percent = int(fin.read().strip())
    with open('/sys/class/power_supply/BAT1/status') as fin:
        if fin.read().strip() == 'Charging':
            charging = True
        else:
            charging = False

    out = ''
    if charging:
        out += '\uf1e6 ' # power cord
    if percent < 25:
        out += '%{{F#bd5a4e}}\uf244 ({}%)%{{F-}}'.format(percent) # 0/4 battery
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
    status = 'on' in info[5]
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
        '%{{l}}{s}{apps}{launcher}'
        '%{{c}}{clock}%'
        '{{r}}{network}{s}{volume}{s}{brightness}{s}{battery}{s}\n'
    ).format(s=SPACING,
             apps=render('apps'),
             launcher=render('launcher'),
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
        self.do_stop = False

    def update_all(self):
        for name in renderers:
            if name != 'launcher':
                update(name)

    def run(self):
        while not self.do_stop:
            self.update_all()
            update_bar(self.bar)
            time.sleep(2)

    def stop(self):
        self.do_stop = True

COMMUNICATION_FILE = os.path.expanduser('~/.cyanbar_pipeinst')
class ListenerThread(threading.Thread):
    """The thread that listens to the COMMUNICATION_FILE for commands."""
    def __init__(self, bar_proc):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.stop = False
        self.bar = bar_proc

    def make_pipeinst(self):
        """Make the pipe file a blank file."""
        with open(COMMUNICATION_FILE, 'w') as fout:
            pass

    def process_command(self, cmd):
        """Process a command."""
        cmd = cmd.strip()
        try:
            update(cmd)
            update_bar(self.bar)
        except Exception as e:
            pass

    def run(self):
        """Continuously listen for commands."""
        self.make_pipeinst()
        with open(COMMUNICATION_FILE, 'r+') as fin:
            while not self.stop:
                where = fin.tell()
                line = fin.readline()
                if not line:
                    time.sleep(.05)
                    fin.seek(where)
                else:
                    # line/command was recieved
                    self.process_command(line)

class LauncherRenderer:
    """The thread that reads the input when typing in an app command."""
    def __init__(self, bar_process):
        self.bar = bar_process
        self.tt_digits_shift = {
            '1':'!','2':'@','3':'#','4':'$','5':'%','6':'^','7':'&','8':'*',
            '9':'(','0':')'}
        self.tt_misc = {
            'GRAVE':'`','MINUS':'-','EQUAL':'=','LEFTBRACE':'[','RIGHTBRACE':']',
            'BACKSLASH':'\\','COMMA':',','DOT':'.','SLASH':'/',
            'SEMICOLON':';','APOSTROPHE':'\'','SPACE':' '}
        self.tt_misc_shift = {
            'GRAVE':'~','MINUS':'_','EQUAL':'+','LEFTBRACE':'{','RIGHTBRACE':'}',
            'BACKSLASH':'|','COMMA':'<','DOT':'>','SLASH':'?',
            'SEMICOLON':':','APOSTROPHE':'"','SPACE':' '}
        self.find_bar_winid()
        self.activated = False

    def find_bar_winid(self):
        """Find the X11 ID of the lemonbar."""
        time.sleep(2)
        for line in subprocess.run(
                'wmctrl -l'.split(), stdout=PIPE).stdout.strip().split(b'\n'):
            fields = line.strip().split()
            if fields[-1] == b'bar' and fields[1] == b'-1':
                self.rootid = fields[0].decode('utf8')
                break

    def kc_to_text(self, kc):
        """(try to) Convert a stripped keycode to text."""
        if kc in string.ascii_uppercase:
            if self.shifted:
                return kc
            return kc.lower()
        elif kc in string.digits:
            if self.shifted:
                return self.tt_digits_shift[kc]
            return kc
        elif kc in self.tt_misc:
            if self.shifted:
                return self.tt_misc_shift[kc]
            return self.tt_misc[kc]
        return None # not a printable, maybe...

    def process_key_event(self, ev):
        """Process a key event."""
        kc = ev.keycode.split('_')[1]
        char = self.kc_to_text(kc)
        if char is not None:
            if ev.keystate == ev.key_down:
                # it was a down-press character
                self.text += char
        else:
            # it wasn't a character.
            if kc in ('LEFTSHIFT', 'RIGHTSHIFT'):
                if ev.keystate != ev.key_hold:
                    self.shifted = not self.shifted
            elif kc == 'ENTER':
                self.submit()
                self.stop()
            elif kc == 'ESC':
                self.stop()
            elif kc == 'BACKSPACE':
                if ev.keystate != ev.key_up:
                    self.text = self.text[:-1]
            elif kc == 'TAB':
                if ev.keystate == ev.key_down:
                    self.autocomplete()

    def autocomplete(self):
        """Try to autocomplete the text."""
        def ac(x, y=None):
            if y is None:
                y = x
            if x.startswith(self.text):
                self.text = y
        ac('firefox')
        ac('urxvt')
        ac('lilyterm', 'urxvt')
        ac('emacs')

    def submit(self):
        """Submit the entered text."""
        # unix double-fork
        pid = os.fork()
        if pid > 0:
            return
        # IN FIRST CHILD
        os.setsid()
        pid = os.fork()
        if pid > 0:
            # IN SECOND PARENT
            sys.exit(0)
        # IN SECOND CHILD; call process
        subprocess.run(self.text, shell=True)
        os._exit(os.EX_OK)

    def disable_input(self):
        """(effectively) Disable input through X11 to all windows."""
        # capture currently active ID
        activewindow = subprocess.run('xdotool getactivewindow'.split(),
                                        stdout=PIPE).stdout
        if activewindow:
            self.return_to = int(activewindow)
        else:
            self.return_to = None
        # lol, switch to the bar... not the best method maybe...
        subprocess.run('xdotool windowactivate {}'.format(self.rootid).split(),
                       stdout=PIPE, stdin=PIPE)

    def enable_input(self):
        """(effectively) Re-enable input through X11."""
        if self.return_to is not None:
            subprocess.run(
                'xdotool windowactivate {}'.format(self.return_to).split())

    def run(self):
        """Thread loop."""
        kbd = evdev.InputDevice('/dev/input/event3') # event3 = keyboard
        hide('apps')
        self.activated = True
        self.disable_input()
        update_bar(self.bar)
        for event in kbd.read_loop():
            if self.do_stop:
                break
            if event.type == evdev.ecodes.EV_KEY:
                event = evdev.categorize(event)
                self.process_key_event(event)
                update_bar(self.bar)
        self.activated = False
        self.enable_input()
        unhide('apps')
        update_bar(self.bar)
        time.sleep(.5)
        update('apps')
        update_bar(self.bar)

    def stop(self):
        self.do_stop = True

    # Renderer-like functions
    def update(self):
        self.text = ''
        self.shifted = False
        self.do_stop = False
        self.thread = threading.Thread(target=self.run)
        self.thread.run()

    def render(self):
        if self.activated:
            return '%{{T3}}%{{B#bd5a4e}}  >  %{{B-}}  {}%{{T-}}'.format(
                self.text)
        return ''

PID_FILE = os.path.expanduser('~/.cyanbar.pid')
LOCK_FILE = os.path.expanduser('~/.cyanbar.lock')
def acquire_lock():
    """Try to get a lock on the LOCK_FILE. Return None on failure."""
    fp = open(LOCK_FILE, 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fp
    except IOError:
        # another instance is running
        fp.close()
        return None

def test_locked():
    """Test if the LOCK_FILE is locked. Return True if locked."""
    fp = open(LOCK_FILE, 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False # automatically unlocks
    except IOError:
        # another instance is running
        return True
    finally:
        fp.close() # this is redundant anyway I think

def save_pid():
    """Save current PID to the PID_FILE."""
    with open(PID_FILE, 'w') as fout:
        fout.write(str(os.getpid()))
def read_pid():
    """Load the PID from file."""
    with open(PID_FILE, 'r') as fin:
        return int(fin.read())
                    
def do_run():
    """Main routine."""
    global renderers
    # open lemonbar
    lock_fp = acquire_lock()
    if lock_fp is None:
        # we are not unique
        sys.stderr.write('Another cyanbar process is already running!\n')
        return 1
    save_pid()
    lemonbar_cmd = ('lemonbar '
                    '-o 0 -f noto:size=22 -o -2 -f fontawesome:size=22 -f notomono:size=22 '
                    '-B #ff2a2a2a -F #ffeeeeee '
                    '-g 3200x50')
    with Popen(lemonbar_cmd.split(), stdout=PIPE, stdin=PIPE,
               bufsize=1, universal_newlines=True) as proc:
        heartbeat = HeartbeatThread(proc)
        listener = ListenerThread(proc)
        renderers['launcher'] = LauncherRenderer(proc)
        heartbeat.start()
        listener.start()
        for line in proc.stdout:
            # each line is a command to run
            Popen(line.strip(), shell=True).wait()
            update('apps')
            update_bar(proc)
        heartbeat.stop()
    lock_fp.close()

def do_kill():
    """Kill the bar."""
    if test_locked():
        # good; something is running.
        os.kill(read_pid(), signal.SIGKILL)
        return 0
    # otherwise nothing is running
    sys.stderr.write('The cyanbar was not running.\n')
    return 1

def do_send_update(words):
    """Send signal(s) to the bar."""
    if test_locked():
        # good; there's something there to listen.
        with open(COMMUNICATION_FILE, 'a') as fout:
            fout.write('\n'.join(words)+'\n')
        return 0
    sys.stderr.write('The cyanbar was not running.\n')
    return 1

def main():
    """Parse arguments and decide main action."""
    parser = argparse.ArgumentParser(
        description='Run and control the bar.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-r', '--run',
                       action='store_true',
                       help='Start the bar.')
    group.add_argument('-k', '--kill',
                       action='store_true',
                       help='Kill the bar process.')
    group.add_argument('-u', '--update',
                       action='append',
                       metavar='element',
                       help="Update a bar element (don't wait for heartbeat).")
    args = parser.parse_args()
    if args.run:
        return do_run()
    elif args.kill:
        return do_kill()
    elif args.update:
        return do_send_update(args.update)

if __name__ == '__main__':
    sys.exit(main())
