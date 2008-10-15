# -*- coding: utf-8 -*-
# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

"""\
A mini anki webserver
======================

This is a quick hack.
"""
__docformat__ = 'restructuredtext'

import time, cgi, sys, os, re, subprocess
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from anki import DeckStorage as ds
from anki.sync import SyncClient, HttpSyncServerProxy
from anki.media import mediaRefs

configFile = os.path.expanduser("~/.ankimini-config.py")
try:
    execfile(configFile)
except:
    print "Can't read the config file. Did you install it?\n"
    raise

print "open deck.. " + DECK_PATH
if not os.path.exists(DECK_PATH):
    raise ValueError("Couldn't find your deck. Please check config.")
deck = ds.Deck(DECK_PATH)

currentCard = None

class Handler(SimpleHTTPRequestHandler):

    def _outer(self):
        return """
<html>
<head>
<title>Anki</title>
<link rel="apple-touch-icon" href="http://ichi2.net/anki/anki-iphone-logo.png"/>
<meta name="viewport" content="user-scalable=yes, width=device-width,
    maximum-scale=0.6667" />
<script type="text/javascript" language="javascript">
<!--
window.addEventListener("load", function() { setTimeout(loaded, 100) }, false);
function loaded() {
window.scrollTo(0, 1); // pan to the bottom, hides the location bar
}
//-->
</script>
</head>
<body>
<iframe src="/question" width=470 frameborder=0 height=700>
</iframe>
</body></html>"""

    def _top(self):
        if deck.modifiedSinceSave():
            saveClass="medButtonRed"
        else:
            saveClass="medButton"
        if self.errorMsg:
            self.errorMsg = '<p style="color: red">' + self.errorMsg + "</p>"
        return """
<html>
<head>
<style>
.bigButton
{ font-size: 18px; width: 450px; height: 50px; padding: 5px;}
.easeButton
{ font-size: 18px; width: 85px; height: 50px; padding: 5px;}
.medButton
{ font-size: 18px; width: 100px; height: 40px; padding: 5px;}
.medButtonRed
{ font-size: 18px; width: 100px; height: 40px; padding: 5px; color: #FF0000; }
.q
{ font-size: 30px; color:#0000ff;}
.a
{ font-size: 30px; }
</style>
</head>
<body>
<table width="100%%"><tr valign=middle><td align=left>
<form action="/save" method="get">
<input class="%s" type="submit" class="button" value="Save">
</form></td>
<td align=center valign=top>
%s
</td>
<td align=right>
<form action="/sync" method="get">
<input class="medButton" type="submit" class="button" value="Sync">
</form></td></tr></table>
%s
""" % (saveClass, self.getStats(), self.errorMsg)

    _bottom = """
</form>
</body>
</html>"""

    def flushWrite(self, msg):
        self.wfile.write(msg + "<br>\n")
        self.wfile.flush()

    def do_GET(self):
        lp = self.path.lower()
        def writeImage():
            self.wfile.write(open(os.path.join(deck.mediaDir(), lp[1:])).read())
        if lp.endswith(".jpg"):
            self.send_response(200)
            self.send_header("Content-type", "image/jpeg")
            self.end_headers()
            writeImage()
            return
        if lp.endswith(".png"):
            self.send_response(200)
            self.send_header("Content-type", "image/png")
            self.end_headers()
            writeImage()
            return
        serviceStart = time.time()
        global currentCard, deck
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        # cgi parms
        try:
            (path, qs) = self.path.split("?")
        except ValueError:
            qs = ""
        query = cgi.parse_qs(qs)
        for k in query:
            query[k] = query[k][0]
        q = query.get("q", None)
        mod = query.get("mod", None)
        self.errorMsg = ""
        buffer = u""

        if self.path.startswith("/switch"):
            new = query.get("d", DECK_PATH)
            success = False
            try:
                newdeck = ds.Deck(os.path.join(
                    os.path.dirname(DECK_PATH),
                    new))
                success = True
            except:
                pass
            if success:
                deck.save()
                deck.close()
                deck = newdeck
            self.path = "/"

        if self.path == "/":
            # refresh
            deck.rebuildQueue()
            self.flushWrite(self._outer())
        elif self.path.startswith("/save"):
            deck.save()
            self.path = "/question"
        elif self.path.startswith("/sync"):
            deck.save()
            deck.lastLoaded = time.time()
            # syncing
            while 1:
                proxy = HttpSyncServerProxy(SYNC_USERNAME, SYNC_PASSWORD)
                try:
                    proxy.connect("ankimini")
                except:
                    self.errorMsg = "Can't sync - check username/password"
                    self.path = "/question"
                    break
                if not proxy.hasDeck(deck.syncName):
                    self.errorMsg = "Can't sync, no deck on server"
                    self.path = "/question"
                    break
                if abs(proxy.timestamp - time.time()) > 60:
                    self.flushWrite(
                        "Your clock is off by more than 60 seconds.<br>"
                        "Syncing will not work until you fix this.")
                    return

                client = SyncClient(deck)
                client.setServer(proxy)
                # need to do anything?
                proxy.deckName = deck.syncName
                if not client.prepareSync():
                    self.errorMsg = "Nothing to do"
                    self.path = "/question"
                    break
                # summary
                self.flushWrite("""
<html><head>
<meta name="viewport" content="user-scalable=yes, width=device-width,
    maximum-scale=0.6667" />
</head><body>\n""")
                self.flushWrite("Fetching summary from server..")
                sums = client.summaries()
                # diff
                self.flushWrite("Determining differences..")
                payload = client.genPayload(sums)
                # send payload
                pr = client.payloadChangeReport(payload)
                self.flushWrite("<br>" + pr + "<br>")
                self.flushWrite("Sending payload...")
                res = client.server.applyPayload(payload)
                # apply reply
                self.flushWrite("Applying reply..")
                client.applyPayloadReply(res)
                # finished. save deck, preserving mod time
                self.flushWrite("Sync complete.")
                deck._countsDirty = True
                deck.markExpiredCardsDue()
                deck.lastLoaded = deck.modified
                deck.s.flush()
                deck.s.commit()
                deck.rebuildQueue()
                self.flushWrite('<br><a href="/question">return</a>')
                self.wfile.write("</body></html>")
                self.wfile.flush()
                break

        if self.path.startswith("/question"):
            # possibly answer old card
            if (q is not None and
                currentCard and mod == str(int(currentCard.modified))):
                deck.answerCard(currentCard, int(q))
            # get new card
            c = deck.getCard(orm=False)
            if not c:
                # try once more after refreshing queue
                deck._countsDirty = True
                deck.markExpiredCardsDue()
                c = deck.getCard(orm=False)
                if not c:
                    buffer += (self._top() +
                               deck.deckFinishedMsg())
            else:
                currentCard = c
                buffer += (self._top() + ("""
<br><div class="q">%(question)s</div>
<br><br>
<form action="/answer" method="get">
<input class="bigButton" type="submit" class="button" value="Answer">
""" % {
        "question": self.prepareMedia(c.question),
        }))
                buffer += (self._bottom)
        elif self.path.startswith("/answer"):
            if not currentCard:
                currentCard = deck.getCard(orm=False)
            c = currentCard
            buffer += (self._top() + """
<br>
<div class="q">%(question)s</div>
<div class="a">%(answer)s</div>
<br><br><form action="/question" method="get">
<input type="hidden" name="mod" value="%(mod)d">
<table width="100%%">
<tr>
""" % {
    "question": self.prepareMedia(c.question, auto=False),
    "answer": self.prepareMedia(c.answer),
    "mod": c.modified,
    })
            for i in range(5):
                qual = deck.nextIntervalStr(c, i)
                buffer += ("""
<td align=center>%s<br>
<input class="easeButton" type="submit" class="button" name="q" value="%d"/>
</td>
""" % (qual, i))
            buffer += ("</tr></table>")
            buffer += (self._bottom)
        self.wfile.write(buffer.encode("utf-8") + "\n")
        print "service time", time.time() - serviceStart

    def getStats(self):
        s = deck.getStats()
        stats = (("T: %(dYesTotal)d/%(dTotal)d "
                 "(%(dYesTotal%)3.1f%%) "
                 "A: %(gMatureYes%)3.1f%%.<br>"
                 "%(failed)d+%(successive)d+%(new)d ETA: %(timeLeft)s") % s)
        return stats

    def prepareMedia(self, string, auto=True):
        for (fullMatch, filename, replacementString) in mediaRefs(string):
            if fullMatch.startswith("["):
                if filename.lower().endswith(".mp3") and auto:
                    subprocess.Popen(["play",
                                      os.path.join(deck.mediaDir(), filename)])
                string = re.sub(re.escape(fullMatch), "", string)
            else:
                pass
                #string = re.sub(re.escape(fullMatch), '''
                #<img src="%(f)s">''' % {'f': relativeMediaPath(filename)}, string)
                #return string
        return string

def run(server_class=HTTPServer,
        handler_class=Handler):
    server_address = ('', SERVER_PORT)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

print "starting server on port %d" % SERVER_PORT
run()
