# test_blocage.py
# Petit test : est-ce que Redbubble (Cloudflare) bloque cette machine ?
# Envoie 10 requêtes d'autocomplétion + 1 page shop, et affiche le résultat.
# Ne touche pas au code principal.
#
# Lancer :  python test_blocage.py           (navigateur caché)
#           python test_blocage.py visible   (navigateur visible, sur ton PC)

import asyncio
import sys
import urllib.request
from playwright.async_api import async_playwright

CLES = ["a", "b", "mo", "cat", "dog", "sun", "art", "love", "anime", "x"]
URL_AUTO = "https://www.redbubble.com/typeahead/?term={}&locale=en"
URL_SHOP = ("https://www.redbubble.com/shop?iaCode=all-departments"
            "&sortOrder=recent&includeMatureContent=false&query=cat")

# Lance fetch() depuis la page redbubble.com (comme dans le code principal)
JS_FETCH = """async (url) => {
    try {
        const r = await fetch(url);
        const t = await r.text();
        return [r.status, t];
    } catch (e) {
        return [0, String(e)];
    }
}"""


def mon_ip():
    try:
        return urllib.request.urlopen("https://api.ipify.org", timeout=10).read().decode()
    except Exception:
        return "inconnue"


def est_challenge(texte):
    return "Just a moment" in texte or "cf-chl" in texte


async def main():
    visible = "visible" in sys.argv
    print("IP de cette machine :", mon_ip())
    print("Navigateur :", "visible" if visible else "caché")
    print("-" * 50)

    ok = 0
    bloque = 0

    async with async_playwright() as p:
        nav = await p.chromium.launch(headless=not visible)
        page = await nav.new_page()

        # 1) Page d'accueil
        try:
            r = await page.goto("https://www.redbubble.com/",
                                wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            titre = await page.title()
            print(f"Accueil : {r.status if r else '?'}  | titre : {titre}")
            if est_challenge(titre):
                print("  -> Page Cloudflare 'Just a moment' : bloqué dès l'accueil")
        except Exception as e:
            print("Accueil : erreur ->", e)

        # 2) Autocomplétion
        for cle in CLES:
            statut, texte = await page.evaluate(JS_FETCH, URL_AUTO.format(cle))
            if statut == 200 and not est_challenge(texte):
                ok += 1
                print(f"Autocomplétion '{cle}' : 200 OK")
            else:
                bloque += 1
                raison = "challenge Cloudflare" if est_challenge(texte) else texte[:80]
                print(f"Autocomplétion '{cle}' : {statut} BLOQUÉ ({raison})")
            await page.wait_for_timeout(300)

        # 3) Page shop (comptage des designs)
        statut, texte = await page.evaluate(JS_FETCH, URL_SHOP)
        if statut == 200 and not est_challenge(texte) and '"pagination"' in texte:
            ok += 1
            print("Page shop 'cat' : 200 OK (pagination trouvée)")
        else:
            bloque += 1
            print(f"Page shop 'cat' : {statut} BLOQUÉ ou format inattendu")

        await nav.close()

    print("-" * 50)
    print(f"Résultat : {ok} OK / {bloque} bloqué(s) sur {ok + bloque}")
    if bloque == 0:
        print("VERDICT : pas de blocage ici, le code peut tourner sur cette machine.")
    elif ok == 0:
        print("VERDICT : bloqué complètement ici.")
    else:
        print("VERDICT : blocage partiel, pas fiable.")


#   RAFALE : ~2000 requêtes au rythme du scan (groupes de 30 + pause 0,1 s)
#   Lancer :  python test_blocage.py visible rafale

JS_GROUPE = """async (urls) => {
    return await Promise.all(urls.map(async (u) => {
        try {
            const r = await fetch(u);
            const t = await r.text();
            const ch = t.includes("Just a moment") || t.includes("cf-chl");
            return (r.status === 200 && !ch) ? 1 : 0;
        } catch (e) { return 0; }
    }));
}"""


def cles_rafale(n=2000):
    lettres = "abcdefghijklmnopqrstuvwxyz"
    cles = [a + b for a in lettres for b in lettres]                      # 676
    cles += [a + b + c for a in lettres for b in lettres for c in lettres]  # 3 lettres
    return cles[:n]


async def rafale():
    import time
    print("IP de cette machine :", mon_ip())
    print("RAFALE : 2000 requêtes, groupes de 30, pause 0,1 s")
    print("-" * 50)
    cles = cles_rafale()
    ok = bloque = 0
    bloque_suite = 0
    debut = time.time()

    async with async_playwright() as p:
        nav = await p.chromium.launch(headless="visible" not in sys.argv)
        page = await nav.new_page()
        await page.goto("https://www.redbubble.com/",
                        wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        for i in range(0, len(cles), 30):
            groupe = [URL_AUTO.format(c) for c in cles[i:i + 30]]
            res = await page.evaluate(JS_GROUPE, groupe)
            ok += sum(res)
            nb_bloques = len(res) - sum(res)
            bloque += nb_bloques
            bloque_suite = bloque_suite + nb_bloques if nb_bloques else 0

            fait = i + len(groupe)
            if fait % 300 < 30 or nb_bloques:
                duree = time.time() - debut
                print(f"{fait}/{len(cles)} | OK {ok} | bloqués {bloque} | "
                      f"{fait / duree:.1f} req/s")

            if bloque_suite >= 60:
                print("ARRÊT : trop de blocages à la suite (Cloudflare a réagi)")
                break
            await page.wait_for_timeout(100)

        await nav.close()

    duree = time.time() - debut
    print("-" * 50)
    print(f"Résultat : {ok} OK / {bloque} bloqué(s) en {duree:.0f} s "
          f"({(ok + bloque) / duree:.1f} req/s)")
    if bloque == 0:
        print("VERDICT : la machine tient le rythme du scan.")
    elif ok > 0 and bloque < 50:
        print("VERDICT : quelques blocages, il faudra ralentir un peu.")
    else:
        print("VERDICT : bloqué à ce rythme.")


if "rafale" in sys.argv:
    asyncio.run(rafale())
else:
    asyncio.run(main())
