# -*- coding: utf-8 -*-
# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

from time import time
from anki import DeckStorage as ds

print "open deck.."
t = time()
d = ds.Deck("tango.anki", rebuild=False)
print "opened in", time() - t
print "rebuild (new)..",
t = time()
d.rebuildQueue()
print time() - t

# timing
for i in range(5):
    t3 = time()
    print "getIds..",
    t = time()
    card = d.getCard(orm=False)
    #cards = d.getCards(orm=False, limit=10)
    #print [c.id for c in cards]
    print time() - t
    t = time()
    print "ans..",
    d.answerCard(card, 1)
    print time() - t; t = time()
    s = d.getStats()
    print "total all", time() - t3
