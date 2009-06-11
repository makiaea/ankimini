# location of ankimini source dir.  We need libank, main.py and timings.py in this dir.
# default is ..
ANKIMINI_SOURCE_DIR=..
LIBANKI_SOURCE_DIR=../..

DEB_VERSION=0.28
UPSTREAM_VERSION=$(shell grep VERSION_ANKIMINI= $(ANKIMINI_SOURCE_DIR)/main.py  | cut -d'"' -f2)

# debian control file package details
DEBIAN_CONTROL_FILE=AnkiMini/DEBIAN/control
CTL_Package=net.ichi2.ankimini
CTL_Name=AnkiMini
CTL_Version=$(UPSTREAM_VERSION)-$(DEB_VERSION)
CTL_Section=Education
CTL_Depends=python, sqlite3, mobilesubstrate, com.ericasadun.utilities
CTL_Recommends=com.bigboss.bossprefs
CTL_Architecture=iphoneos-arm
CTL_Description=Anki server on iPhone.  Access with Safari (http://localhost:8000).
CTL_Icon=file:///Applications/AnkiMini.app/Icon.png
CTL_Author=Richard Colley <richard.colley+ankimini@gmail.com>
CTL_Homepage=http://ichi2.net/anki
CTL_Maintainer=Damien Elmes <resolve@ichi2.net>


all: AnkiMini AnkiMini-$(DEB_VERSION).deb Packages.bz2

AnkiMini:
	@echo "Copying ankimini v$(UPSTREAM_VERSION)"
	-mv AnkiMini AnkiMini.old
	cp -rp directory-template AnkiMini
	cp -rp $(ANKIMINI_SOURCE_DIR)/main.py $(ANKIMINI_SOURCE_DIR)/timings.py AnkiMini/Applications/AnkiMini.app/
	# clean .pyc files from libanki
	find $(LIBANKI_SOURCE_DIR)/libanki -type f ! -path $(LIBANKI_SOURCE_DIR)/.git/\* -name '*.pyc' -exec rm {} \;
	# avoid copying .git
	cp -rp $(LIBANKI_SOURCE_DIR)/libanki/* AnkiMini/Applications/AnkiMini.app/libanki/

AnkiMini-$(DEB_VERSION).deb: AnkiMini $(DEBIAN_CONTROL_FILE)
	echo "Making $@"
	PATH=$$PATH:bin dpkg-deb -b AnkiMini
	mv --backup=numbered AnkiMini.deb $@

Packages-$(DEB_VERSION): $(DEBIAN_CONTROL_FILE) AnkiMini-$(DEB_VERSION).deb
	echo "Making $@,$*,$?"
	cp $(DEBIAN_CONTROL_FILE) $@
	echo "Filename: AnkiMini-$(DEB_VERSION).deb" >>$@
	echo "Size: $(shell ls -l AnkiMini-$(DEB_VERSION).deb  | cut -d' ' -f5)" >>$@
	echo "MD5sum: $(shell md5sum AnkiMini-$(DEB_VERSION).deb  | cut -d' ' -f1)" >>$@

Packages.bz2: Packages-$(DEB_VERSION)
	bzip2 <$< >$@

$(DEBIAN_CONTROL_FILE):
	echo "Making $@"
	echo "Package: $(CTL_Package)" > $@
	echo "Name: $(CTL_Name)" >>$@
	echo "Version: $(CTL_Version)" >>$@
	echo "Section: $(CTL_Section)" >>$@
	echo "Depends: $(CTL_Depends)" >>$@
	echo "Recommends: $(CTL_Recommends)" >>$@
	echo "Architecture: $(CTL_Architecture)" >>$@
	echo "Description: $(CTL_Description)" >>$@
	echo "Icon: $(CTL_Icon)" >>$@
	echo "Author: $(CTL_Author)" >>$@
	echo "Homepage: $(CTL_Homepage)" >>$@
	echo "Maintainer: $(CTL_Maintainer)" >>$@

clean:
	-rm AnkiMini.deb AnkiMini-$(DEB_VERSION).deb Packages-$(DEB_VERSION) Packages.bz2

virginal: clean
	-rm -rf AnkiMini AnkiMini.old
