import json, sys, time
from urllib.parse import quote_plus
sys.path.insert(0, "src")
from aipc.browser.control import BrowserControl, LINKS_JS
bc = BrowserControl(load_timeout=15)
bc._start("about:blank")
Q = ["ราคาทองวันนี้", "วิธีทำไข่เจียว", "พยากรณ์อากาศเชียงใหม่", "ร้านซ่อมรถใกล้ฉัน"]
ENG = {"bing": "https://www.bing.com/search?setlang=th&q=", "bing-plain": "https://www.bing.com/search?q=",
       "ddg": "https://html.duckduckgo.com/html/?q=", "ddg-js": "https://duckduckgo.com/?kl=th-th&q="}
for rnd in range(2):
    for name, base in ENG.items():
        for q in Q:
            url = bc._go(base + quote_plus(q))
            time.sleep(1.0)
            links = bc._eval(LINKS_JS) or []
            print(rnd, name, q, "|", url[:60], "|", " ; ".join((l["text"][:28] + " " + l["href"].split("/")[2]) for l in links[:3]), flush=True)
bc.close()
