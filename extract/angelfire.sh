sed -i "s/center>/span>/gi" *html
mkdir utf8
ls -1 *html | while read a; do echo "Converting $a..." ; cs=`chardetect "$a" | cut -f2- -d":" | cut -f2 -d" "`; if [ "x$cs" == "xno" ]; then cs=`uchardet "$a"`; fi; iconv -f "$cs" -t utf-8 "$a" > "utf8/$a"; done
mkdir utf8/dump
cd utf8
ls *html | while read a; do elinks   -eval 'set document.css.enable = 1'   -eval 'set document.css.ignore_display_none = 0'   -eval 'set document.css.stylesheet = "'"$PWD"'/clean.css"'   -dump -dump-width 150 -dump-charset "utf-8" "$a" > "dump/$a.mxp"; done
