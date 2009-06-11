#!/bin/sh

OLDER_ANKI_DIR=~mobile
OLDER_CONFIG_FILE=.ankimini-config.py
OLD_CONFIG_FILE=ankimini-config.py
NEW_CONFIG_FILE=$OLD_CONFIG_FILE
OLD_ANKI_DIR=~mobile/Library/AnkiMini
NEW_ANKI_DIR=~mobile/.anki
APP_DIR=/Applications/AnkiMini.app

set_perms()
{
  recurse=
  [ "$1" = -R ] && { recurse=-R ; shift; }
  owner_group=$1
  perms=$2
  shift 2

  chown $recurse $owner_group "$@"
  if [ "$recurse" = -R ]; then
    find "$@" -type f -exec chmod $perms {} \;
    find "$@" -type d -exec chmod +x {} \;
  else
    chmod $perms "$@"
  fi
}

# set perms on anki config/deck directory and files
set_perms -R mobile:mobile 644 $NEW_ANKI_DIR

# set perms on ankimini application directory
set_perms -R mobile:mobile 644 $APP_DIR
chmod 755 $APP_DIR/ankimini $APP_DIR/Anki $APP_DIR/fixperms.sh

# set perms on boss prefs and launchctl files
set_perms root:wheel 644 /Applications/BossPrefs.app/services/AnkiMini
set_perms root:wheel 644 /Library/LaunchDaemons/net.ichi2.ankimini.plist

# set perms on python eggs
set_perms root:wheel 644 /usr/lib/python2.5/site-packages/ankimini.pth
set_perms -R root:wheel 644 /usr/lib/python2.5/site-packages/SQLAlchemy-0.4.7p1-py2.5.egg
set_perms root:wheel 644 /usr/lib/python2.5/site-packages/simplejson*

