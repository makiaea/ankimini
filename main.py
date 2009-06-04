# -*- coding: utf-8 -*-
# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
#

"""\
A mini anki webserver
======================
"""
__docformat__ = 'restructuredtext'

import time, cgi, sys, os, re, subprocess
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from anki import DeckStorage as ds
from anki.sync import SyncClient, HttpSyncServerProxy
from anki.media import mediaRefs
from anki.utils import parseTags, joinTags
from anki.facts import Fact



####### VERSIONS #########

from anki import version as VERSION_LIBANKI
VERSION_ANKIMINI="1.1.8.rlc7"

##########################

ANKIMINI_PATH=os.path.join(os.path.expanduser("~/"),".anki")

class Config(dict):
    configFile = os.path.join(ANKIMINI_PATH,"ankimini-config.py")
    re_matchComments = re.compile('#.*')
    re_matchConfig = re.compile('\s*(\w+)\s*=([^#]*)')

    def __init__(self, filename=None ):
        dict.__init__(self)
        self.setDefaults()
        if filename:
          self.configFile = filename

    # setup some defaults in case problems reading config file
    def setDefaults(self):
        self['DEBUG_NETWORK']=False
        self['SERVER_PORT']=8000
        self['DECK_PATH']=os.path.join(ANKIMINI_PATH,"sample-deck.anki")
        self['SYNC_USERNAME']="changeme"
        self['SYNC_PASSWORD']="changeme"
        self['PLAY_COMMAND']="play"

    def loadConfig(self):
        try:
            import re
            for line in open(self.configFile,"r").readlines():
                line = self.re_matchComments.sub("", line)		# remove comments
                match = self.re_matchConfig.match(line)
                if match:
                    k = match.group(1)
                    v = match.group(2)
                    self[k] = eval(v)
        except Exception, e:
            print "Can't read the config file. Did you install it?\n"
            print e
            print "Reverting to defaults\n"
            self.setDefaults()
            self.saveConfig()
    #end loadConfig()

    def saveConfig(self):
        outfile = open(self.configFile, "w")
        outfile.write("# auto generated, manual changes may be overwritten\n")
        for k in self.keys():
            outfile.write( "%s=%s\n" % (k, repr(self[k])) )
        outfile.close()
    #end save()



def expandDeckName( raw, base_dir=ANKIMINI_PATH ):
    if raw[0] == '/':
        canonical = raw
    else:
        canonical = os.path.join(base_dir, raw)

    if canonical[-5:] != ".anki":
        canonical += ".anki"

    return canonical
# expandDeckName()

def openDeck(deckPath=None):
    global config
    try:
        if deckPath is None:
            deckPath = config['DECK_PATH']
        deckPath = expandDeckName(deckPath)
        print "open deck.. " + deckPath
        if not os.path.exists(deckPath):
            raise ValueError("Couldn't find deck " % (deckPath,) )
        deck = ds.Deck(deckPath, backup=False)
        deck.s.execute("pragma cache_size = 1000")
    except Exception, e:
        print "Error loading deck"
        print e
        deck = None
    return deck
#end openDeck()

def switchDeck( olddeck, newdeck_name ):
    global config
    newdeck_path = expandDeckName(newdeck_name)
    if olddeck:
        olddeck.save()
        if newdeck_path == olddeck.path:
            raise Exception( "Deck %s already active." % ( newdeck_path, ) )
        print "switching from %s to %s" % ( olddeck.path, newdeck_path )

    newdeck = openDeck(newdeck_path)
    if olddeck:
        olddeck.close()
    return newdeck
# switchDeck()


##################

class Handler(SimpleHTTPRequestHandler):
    def setup(self):
       SimpleHTTPRequestHandler.setup(self)
       if config.get('DEBUG_NETWORK') == True:
           class FileProxy:
               file=None
               def __init__(self, file):
                   self.file=file
               def write(self,data):
                   print data
                   self.file.write(data)
               def __getattr__(self, name):
                   return getattr(self.file, name)
               def __setattr__(self, name, value):
                   if name in dir(self): self.__dict__[name] = value
                   else: setattr(self.file, name, value)

           self.wfile = FileProxy(self.wfile)

    def _outer(self):
        return """
<html>
<head>
<title>Anki</title>
<link rel="apple-touch-icon" href="http://ichi2.net/anki/anki-iphone-logo.png"/>
<meta name="viewport" content="user-scalable=yes, width=device-width,
  initial-scale=0.6667" />
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
        if deck and deck.modifiedSinceSave():
            saveClass="medButtonRed"
        else:
            saveClass="medButton"
        if deck and currentCard and deck.s.scalar(
            "select 1 from facts where id = :id and tags like '%marked%'",
            id=currentCard.factId):
            markClass = "medButtonRed"
        else:
            markClass = "medButton"
        if self.errorMsg:
            self.errorMsg = '<p style="color: red">' + self.errorMsg + "</p>"
        if deck:
            stats = self.getStats()
        else:
            stats = ("","")
        return """
<html>
<head>
<style>
.bigButton
{ font-size: 18px; width: 450px; height: 150px; padding: 5px;}
.easeButton
{ font-size: 18px; width: 105px; height: 130px; padding: 5px;}
.easeButtonB
{ font-size: 18px; width: 170px; height: 180px; padding: 5px;}
.medButton
{ font-size: 18px; width: 100px; height: 40px; padding: 5px;}
.medButtonRed
{ font-size: 18px; width: 100px; height: 40px; padding: 5px; color: #FF0000; }
.q
{ font-size: 30px; color:#0000ff;}
.a
{ font-size: 30px; }
body { margin-top: 0px; padding: 0px; }
</style>
</head>
<body>
<table width="100%%">
<tr valign=middle><td align=left>%s</td>
<td align=right>%s</td></table>
<table width="100%%"><tr valign=middle><td align=left>
<form action="/save" method="get">
<input class="%s" type="submit" class="button" value="Save">
</form></td>
<td align=left>
<form action="/mark" method="get">
<input class="%s" type="submit" class="button" value="Mark">
</form></td>
<td align=right>
<form action="/replay" method="get">
<input class="medButton" type="submit" class="button" value="Replay">
</form></td>
<td align=right>
<form action="/sync" method="get">
<input class="medButton" type="submit" class="button" value="Sync">
</form></td>
<td align=right>
</tr></table>
%s
""" % (stats[0], stats[1], saveClass, markClass, self.errorMsg)

    _bottom = """
<br />
<br />
<br />
<table width="100%%"><tr valign=middle>
<td align=left>
<form action="/config" method="get">
<input class="medButton" type="submit" class="button" value="Config">
</form></td>
<td align=left>
<form action="/local" method="get">
<input class="medButton" type="submit" class="button" value="Local">
</form></td>
<td align=right>
<form action="/personal" method="get">
<input class="medButton" type="submit" class="button" value="Online">
</form></td>
<td align=right>
<form action="/about" method="get">
<input class="medButton" type="submit" class="button" value="About">
</form></td>
</table>
</body>
</html>"""

    def flushWrite(self, msg):
        self.wfile.write(msg+"\n")
        self.wfile.flush()

    def lineWrite(self, msg):
        self.flushWrite("<br />"+msg)

######################

    def render_get_config(self):
        global config
        buffer = """
		<html>
		<head><title>Config</title></head>
		<body>
		<h1>Config</h1>
		 <form action="/config" method="POST">
		  <fieldset><legend>Sync details</legend>
		   <label for="username">User name</label> <input id="username" type="text" name="username" value="%s" autocorrect="off" autocapitalize="off" /> <br />
		   <label for="password">Password</label>  <input id="password" type="password" name="password" value="%s" autocorrect="off" autocapitalize="off" />
		  </fieldset>
		  <fieldset><legend>Deck</legend>
		   <label for="deckpath">Deck</label>  <input id="deckpath" type="text" name="deckpath" value="%s" autocorrect="off" autocapitalize="off" />
                   <em>(port change doesn't take effect until a server restart)</em>
		  </fieldset>
		  <fieldset><legend>Misc details</legend>
		   <label for="play">Play command</label>  <input id="play" type="text" name="play" value="%s" autocorrect="off" autocapitalize="off" /> <br />
		   <label for="port">Server port</label>  <input id="port" type="text" name="port" value="%s" autocorrect="off" autocapitalize="off" />
                   <em>(port change doesn't take effect until a server restart)</em>
		  </fieldset>
		  <fieldset class="submit">
		   <input type="submit" class="button" value="Save Config">
		  </fieldset>
		 </form>
		 <br /><a href="/question">return</a>
		</body>
		</html>
        """ % ( config.get('SYNC_USERNAME',''), config.get('SYNC_PASSWORD',''), config.get('DECK_PATH',''),
                 config.get('PLAY_COMMAND',''), config.get('SERVER_PORT','') )

        return buffer
####################### end render_get_config

    def render_post_config(self, params):
        global config
        buffer = "<html><head><title>Config ...</title></head>"
        errorMsg = ""
        try:
            username = unicode(params['username'][0], 'utf-8')
            password = unicode(params['password'][0], 'utf-8')
            deckpath = unicode(params['deckpath'][0], 'utf-8')
            port = int(params['port'][0])
            play = unicode(params['play'][0], 'utf-8')

            config.update( { 'SYNC_USERNAME': username, 'SYNC_PASSWORD': password,
                              'SERVER_PORT': port, 'PLAY_COMMAND': play } )
            config.saveConfig()
            try:
                global deck
                deck = switchDeck( deck, deckpath )
                conifg['DECK_PATH']=deck.path
                config.saveConfig()
                deck.rebuildQueue()
            except Exception, e:
                errorMsg += "<br /><br />Deck didn't change: " + str(e)

            obscured = '*' * len(password)
            buffer += """
		<em>Config saved</em> <br />
		username = %s <br />
		password = %s <br />
                port = %d <br />
                play = %s <br />
                %s
		""" % ( username, obscured, port, play, errorMsg )
        except Exception, e:
            buffer += "<em>Config save may have failed!  Please check the values and try again</em><br />"
            buffer += str(e)

        buffer += """
		<br /><a href="/question">return</a>
		</body></html>
		"""

        return buffer
####################### end render_post_config

    def render_get_local(self):
        import glob
        buffer = """
		<html>
		<head><title>List local decks</title></head>
		<body>
		<h1>Local Decks</h1>
		"""
        try:
            deckList = [ f[:-5] for f in glob.glob(os.path.join(ANKIMINI_PATH,"*.anki")) ]
            if deckList is None or len(deckList)==0:
                buffer += "<em>You have no local decks!</em>"
            else:
                buffer += '<table width="100%%" cellspacing="10">'
                for d in deckList:
                   	buffer += '<tr><td><a href="/switch?d=%s&i=y">%s</a></td></tr>' % ( d, d )
                buffer += "</table>"
        except Exception, e:
            buffer += "<em>Error listing files!</em><br />" + str(e)

        buffer += """
		<br /><a href="/question">return</a>
		</body>
		</html>
	        """

        return buffer
####################### end render_get_local

    def render_get_personal(self):
        global config
        buffer = """
		<html>
		<head><title>List personal decks</title></head>
		<body>
		<h1>Online Personal Decks</h1>
		Please select one to download it...
		"""
        try:
            proxy = HttpSyncServerProxy(config.get('SYNC_USERNAME'), config.get('SYNC_PASSWORD'))
            deckList = proxy.availableDecks()
            if deckList is None or len(deckList)==0:
                buffer += "<em>You have no online decks!</em>"
            else:
                buffer += '<table width="100%%" cellspacing="10">'
                for d in deckList:
                   	buffer += '<tr height><td><a href="/download?deck=%s">%s</a></td></tr>' % ( d, d )
                buffer += "</table>"
        except:
            buffer += "<em>Can't connect - check username/password</em>"

        buffer += """
		<br /><a href="/question">return</a>
		</body>
		</html>
	        """

        return buffer
####################### end render_get_personal

    def render_get_download(self, params):
        global deck
        global config
        global ANKIMINI_PATH

        import tempfile

        name = params["deck"]
        self.wfile.write( """
		<html>
		<head><title>Downloading %s ...</title></head>
		<body>
		""" % ( name ) )
        buffer=""

        tmp_dir=None
        try:
            if deck:
                deck.save()
            local_deck = expandDeckName(name)
            if os.path.exists(local_deck):
                raise Exception("Local deck %s already exists.  You can't overwrite, sorry!" % (name,))

            tmp_dir = unicode(tempfile.mkdtemp(dir=ANKIMINI_PATH, prefix="anki"), sys.getfilesystemencoding())
            tmp_deck = expandDeckName(name, tmp_dir)

            newdeck = ds.Deck(tmp_deck)
            newdeck.s.execute("pragma cache_size = 1000")
            newdeck.modified = 0
            newdeck.s.commit()
            newdeck.syncName = unicode(name)
            newdeck.lastLoaded = newdeck.modified

	    self.syncDeck( newdeck )

            newdeck.save()
            if deck:
                deck.close()
                deck = None
            newdeck.close()
            os.rename(tmp_deck, local_deck)
            config['DECK_PATH']=local_deck
            config.saveConfig()
            deck = openDeck()

        except Exception, e:
            buffer += "<em>Download failed!</em><br />"
            buffer += str(e)
            print "render_get_download(): exception: " + str(e)
        finally:
            if tmp_dir:
                try:
                    os.remove(tmp_deck)
                    os.remove(tmp_deck+"-journal")
                except:
                    pass
                try:
                    os.rmdir(tmp_dir)
                except:
                    pass

        buffer += """
		<br />
		<a href="/question">return</a>
		</body></html>
		"""

        return buffer
####################### end render_get_download

    def render_get_about(self):
        global deck
        global config

        obscured='*' * len(config.get('SYNC_PASSWORD',''))
        buffer = """
            <html>
            <head><title>About</title></head>
            <body>
            <h1>AnkiMini v%s</h1>
            <h2>Currently Loaded Deck</h2>
            %s
            <h2>Versions</h2>
            <table width="100%%">
		<tr><th align="left">Component</th><th align="left">Version</th></tr>
                <tr><td>Ankimini</td><td>%s</td></tr>
                <tr><td>libanki</td><td>%s</td></tr>
            </table>
            <h2>Current config</h2>
            <table width="100%%">
                <tr><td>Config path</td><td>%s</td></tr>
                <tr><td>Deck path</td><td>%s</td></tr>
                <tr><td>Sync user</td><td>%s</td></tr>
                <tr><td>Sync pass</td><td>%s</td></tr>
                <tr><td>Server port</td><td>%s</td></tr>
                <tr><td>Play command</td><td>%s</td></tr>
            </table>
            <p>For more info on Anki, visit the <a href="http://ichi2.net/anki">home page</a></p>
	    <br /><a href="/question">return</a>
            </body>
            </html>
        """ % ( VERSION_ANKIMINI,
		deck.path if deck is not None else 'None',
		VERSION_ANKIMINI, VERSION_LIBANKI,
		config.configFile, config.get('DECK_PATH'), config.get('SYNC_USERNAME'),
                     obscured, config.get('SERVER_PORT'), config.get('PLAY_COMMAND'),
              )

        return buffer
####################### end render_get_about

    def do_POST(self):
        history.append(self.path)
        serviceStart = time.time()
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        length = int(self.headers.getheader('content-length'))
        qs = self.rfile.read(length)
        params = cgi.parse_qs(qs, keep_blank_values=1)

        if self.path.startswith("/config"):
	    buffer = self.render_post_config(params)

        self.wfile.write(buffer.encode("utf-8") + "\n")
        print "service time", time.time() - serviceStart
    #end do_POST()

    def do_GET(self):
        global config
        self.played = False
        lp = self.path.lower()
        def writeImage():
            try:
                self.wfile.write(open(os.path.join(deck.mediaDir(), lp[1:])).read())
            except:
                pass
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
        history.append(self.path)
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
            new = query.get("d", config.get('DECK_PATH',''))
            try:
                deck = switchDeck(deck, new)
                config['DECK_PATH']=deck.path
                config.saveConfig()
                deck.rebuildQueue()
            except Exception, e:
                self.errorMsg = str(e)
            if query.get("i"):
                self.path="/question"
            else:
                self.path="/"

        if self.path == "/":
            # refresh
            if deck:
                deck.rebuildQueue()
            self.flushWrite(self._outer())
        elif deck and self.path.startswith("/save"):
            deck.save()
            self.path = "/question"
        elif deck and self.path.startswith("/mark"):
            f = deck.s.query(Fact).get(currentCard.factId)
            if "marked" in f.tags.lower():
                t = parseTags(f.tags)
                t.remove("Marked")
                f.tags = joinTags(t)
            else:
                f.tags = joinTags(parseTags(
                    f.tags) + ["Marked"])
            f.setModified()
            deck.flushMod()
            deck.s.flush()
            deck.s.expunge(f)
            history.pop()
            self.path = "/question"
        elif deck and self.path.startswith("/replay"):
            self.prepareMedia(currentCard.question)
            self.prepareMedia(currentCard.answer)
            history.pop()
            self.path = "/question"
        elif deck and self.path.startswith("/sync"):
            deck.save()
            deck.lastLoaded = time.time()
            # syncing
            try:
                self.flushWrite("""
			<html><head>
			<meta name="viewport" content="user-scalable=yes, width=device-width, maximum-scale=0.6667" />
			</head><body>""")
                self.syncDeck( deck )
                self.flushWrite('<br><a href="/question">return</a>')
                self.flushWrite("</body></html>")
            except Exception, e:
                self.errorMsg = str(e)
                self.path = "/question"


        if self.path.startswith("/question"):
            if not deck:
                self.errorMsg = "No deck opened! Check config is correct."
                buffer += (self._top() + self._bottom)
            else:
                # possibly answer old card
                if (q is not None and
                    currentCard and mod == str(int(currentCard.modified))):
                    deck.answerCard(currentCard, int(q))
                # get new card
                c = deck.getCard(orm=False)
                if not c:
                    buffer += (self._top() +
                               deck.deckFinishedMsg() +
                               self._bottom)
                else:
                    currentCard = c
                    buffer += (self._top() + ("""
<br><div class="q">%(question)s</div>
<br><br>
<form action="/answer" method="get">
<input class="bigButton" type="submit" class="button" value="Answer">
</form>
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
            ints = {}
            for i in range(1, 5):
                ints[str(i)] = deck.nextIntervalStr(c, i, True)
            buffer += ("""
<td><button class="easeButton" type="submit" class="button" name="q"
value="1">Soon</button></td>
<td><button class="easeButton" type="submit" class="button" name="q"
value="2">%(2)s</button><br></td>
<td><button class="easeButton" type="submit" class="button" name="q"
value="3">%(3)s</button></td>
<td><button class="easeButton" type="submit" class="button" name="q"
value="4">%(4)s</button></td>
""" % ints)
            buffer += ("</tr></table></form>")
            buffer += (self._bottom)

        elif self.path.startswith("/config"):
	    buffer = self.render_get_config()
	elif self.path.startswith("/local"):
	    buffer = self.render_get_local()
	elif self.path.startswith("/personal"):
	    buffer = self.render_get_personal()
	elif self.path.startswith("/download"):
	    buffer = self.render_get_download(query)
	elif self.path.startswith("/about"):
	    buffer = self.render_get_about()
		
        self.wfile.write(buffer.encode("utf-8") + "\n")
        print "service time", time.time() - serviceStart

########################

    def syncDeck(self, deck):
        try:
            proxy = HttpSyncServerProxy(config.get('SYNC_USERNAME'), config.get('SYNC_PASSWORD'))
            proxy.connect("ankimini")
        except:
            raise Exception("Can't sync - check username/password")
        if not proxy.hasDeck(deck.syncName):
            raise Exception("Can't sync, no deck on server")
        if abs(proxy.timestamp - time.time()) > 60:
            raise Exception("Your clock is off by more than 60 seconds.<br>" \
                            "Syncing will not work until you fix this.")

        client = SyncClient(deck)
        client.setServer(proxy)
        # need to do anything?
        proxy.deckName = deck.syncName
        if not client.prepareSync():
            raise Exception("Nothing to do")

	self.flushWrite("""<h1>Syncing deck</h1>
        <h2%s</h2>
	<em>This could take a while with a big deck ... please be patient!</em>
	""" % (deck.path,) )

        # hack to get safari to render immediately!
        self.flushWrite("<!--" + " "*1024 + "-->")

        # summary
        self.lineWrite("Fetching summary from server..")
        sums = client.summaries()
        # diff
        self.lineWrite("Determining differences..")
        payload = client.genPayload(sums)
        # send payload
        pr = client.payloadChangeReport(payload)
        self.lineWrite("<br>" + pr + "<br>")
        self.lineWrite("Sending payload...")

	# this can take a long time ... ensure the client doesn't timeout before we finish
	from threading import Event, Thread
	ping_event = Event()
        def ping_client( s = self.wfile, ev=ping_event ):
            while 1:
                ev.wait(3)
                if ev.isSet():
                    return
                s.write(".<!--\n-->")
                s.flush()
	ping_thread = Thread(target=ping_client)
	ping_thread.start()

        res = client.server.applyPayload(payload)
        # apply reply
        self.lineWrite("Applying reply..")
        client.applyPayloadReply(res)
        # finished. save deck, preserving mod time
        self.lineWrite("Sync complete.")
        deck.rebuildQueue()
        deck.lastLoaded = deck.modified
        deck.s.flush()
        deck.s.commit()

	# turn of client ping
	ping_event.set()
        ping_thread.join(5)



    def getStats(self):
        s = deck.getStats()
        stats = (("T: %(dYesTotal)d/%(dTotal)d "
                 "(%(dYesTotal%)3.1f%%) "
                 "A: <b>%(gMatureYes%)3.1f%%</b>. ETA: <b>%(timeLeft)s</b>") % s)
        f = "<font color=#990000>%(failed)d</font>"
        r = "<font color=#000000>%(rev)d</font>"
        n = "<font color=#0000ff>%(new)d</font>"
        if currentCard:
            if currentCard.reps:
                if currentCard.successive:
                    r = "<u>" + r + "</u>"
                else:
                    f = "<u>" + f + "</u>"
            else:
                n = "<u>" + n + "</u>"
        stats2 = ("<font size=+2>%s+%s+%s</font>" % (f,r,n)) % s
        return (stats, stats2)

    def prepareMedia(self, string, auto=True):
        for (fullMatch, filename, replacementString) in mediaRefs(string):
            if fullMatch.startswith("["):
                if auto and (filename.lower().endswith(".mp3") or
                             filename.lower().endswith(".wav")):
                    if not self.played:
                        subprocess.Popen([PLAY_COMMAND,
                                          os.path.join(deck.mediaDir(), filename)])
                        self.played = True
                string = re.sub(re.escape(fullMatch), "", string)
            else:
                pass
                #string = re.sub(re.escape(fullMatch), '''
                #<img src="%(f)s">''' % {'f': relativeMediaPath(filename)}, string)
                #return string
        return string

def run(server_class=HTTPServer,
        handler_class=Handler):
    global config
    server_address = ('127.0.0.1', config.get('SERVER_PORT',8000))		# explicit 127.0.0.1 so that delays aren't experienced if wifi/3g networks are not reliable
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()



######## main

if __name__ == '__main__':
    config = Config()
    config.loadConfig()
    deck = openDeck()
    currentCard = None
    history = []
    print "starting server on port %d" % config.get('SERVER_PORT',8000)
    run()


