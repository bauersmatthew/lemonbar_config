#!/usr/bin/env bash

SPACING="          "

get_real_windows() {
    for id in $(xdotool search . 2> /dev/null); do
	if [[ $(xprop -id $id | grep '_OB_APP_TYPE(UTF8_STRING) = "normal"' | wc -l) != 0 ]]; then
	    echo $id
	fi
    done
}
apps() {
    winids=$(get_real_windows)
    input=""
    for id in $winids; do
	class=$(xprop -id $id | grep _OB_APP_CLASS | sed -r 's/_OB_APP_CLASS\(UTF8_STRING\) = "([^)]*)"/\1/')
	input="$input;;$id|$class"
    done
    echo "$(mybarutil-apps.py $input $(xdotool getactivewindow))"
}

clock() {
    date +%l:%M
}

battery() {
    val="$(mypolybarutil-battery.py)"
    lpar="("
    if [[ "$(echo $val | grep $lpar)" != "" ]]; then
	val="%{F#bd5a4e}$val%{F-}"
    fi
    echo "$val$SPACING"
}
brightness() {
    echo "$(mypolybarutil-backlight.py)$SPACING"
}
volume() {
    echo "$(mypolybarutil-volume.py | sed 's/(.*)//')$SPACING"
}
network() {
    if [[ $(/usr/sbin/iw wlp2s0 link) != "Not connected." ]]; then
	echo "$SPACING"
    else
	echo "%{F#bd5a4e}%{F-}$SPACING"
    fi
}

wrap() {
    while true; do
	echo "%{l}$(apps)%{c}$(clock)%{r}$(network)$(volume)$(brightness)$(battery)"
	sleep .5
    done
}

wrap | lemonbar \
	   -o 0 -f noto:size=22 -o -2 -f fontawesome:size=22 \
	   -B "#ff2a2a2a" -F "#ffeeeeee" \
	   -g "3200x50" \
     | mybarutil-runlines.py
