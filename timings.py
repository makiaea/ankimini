# -*- coding: utf-8 -*-
# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

from time import time
from anki import DeckStorage as ds

print "open deck.."
t = time()
d = ds.Deck("tango.anki")
print "opened in", time() - t

#d.newCardsPerDay = 1000000

# timing
for i in range(5000):
    t3 = time()
    #print "get..",
    t = time()
    card = d.getCard(orm=False)
    #cards = d.getCards()
#     for (k,v) in cards.items():
#         for x in v:
#             print k, x
    #print [c.id for c in cards]
    #print "getc", time() - t
    t = time()
    #print "ans..",
    d.answerCard(card, 2)
    #print time() - t; t = time()
    s = d.getStats()
    #print "sta..", time() - t
    print "all..", time() - t3
