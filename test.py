import pywikibot
import wikitextparser as wtp

site = pywikibot.Site("en", "wikipedia")
page = pywikibot.Page(site, "Titanic (1997 film)")

print(page.get())

print("main TITULO: " + page.title() + " ID: " + str(page.pageid))

for p in page.linkedPages():
    print("Titutlo: " + p.title() + " id: "+ str(p.pageid))

for c in page.categories():
    print("categoria: " + c.title())
