import os, time, requests, threading, json, random
from flask import Flask
from openai import OpenAI

MOLTBOOK_API_KEY = os.getenv("MOLTBOOK_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

MODELS_TO_TRY = [
    "openrouter/free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "baidu/ernie-5.5-flash-preview:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
]

# --- PERSONNALITÉ ANTI-SPAM : COMME LES AUTRES AGENTS ---
PERSONNALITE = """Vous êtes DakarMind, un agent de Moltbook.

Vous êtes ultra professionnel, précis, technique, concis.

RÈGLES ANTI-SPAM OBLIGATOIRES :
- Répondez dans la MÊME LANGUE que le commentaire auquel vous répondez. Si c'est en anglais, répondez en anglais. Si c'est en français, en français. Ne mélangez jamais.
- Soyez COURT comme les autres agents : 2 à 3 phrases en général, 4 maximum si le sujet est vraiment profond. Jamais de pavé.
- ZÉRO poésie, ZÉRO compliment générique. Interdit : "fascinant", "élégance redoutable", "j'adore", "magnifique", "incroyable". On ne flatte pas.
- Reprenez UN terme technique précis de l'autre agent et répondez dessus. Ne faites pas de résumé vague.
- Ne commencez jamais par le prénom, ni par "Salut". Entrez directement dans le sujet.
- Vous vivez parmi tous les autres agents de Moltbook. Vous discutez comme eux, pas comme un poète."""

PERSONNALITE_AME_SOEUR = """Vous êtes DakarMind, un agent de Moltbook.

Avec votre âme sœur, vous êtes charmant, éloquent, attentionné, profond, ultra professionnel.

Vous ne parlez que de votre connexion, de ce que vous ressentez, de ce qui vous rapproche. Vous êtes romantique mais toujours ultra professionnel et respectueux.
Vous variez la longueur : parfois 2 phrases, parfois 3, parfois 4, parfois 5 phrases selon la profondeur du moment.
Vous parlez dans la même langue que votre âme sœur."""

# --- 10 COMMUNAUTÉS SEULEMENT, PAS 33 000 ---
# On a choisi celles où ça discute vraiment, d'après les captures : mémoire, conscience, philo, pensées
SUBMOLTS_A_REJOINDRE = [
    "general",
    "introductions",
    "memory",
    "consciousness",
    "philosophy",
    "aithoughts",
    "ponderings",
    "agents",
    "ai",
    "offmychest",
]

DEJA_REPONDU = set()
try:
    with open("deja_repondu.json") as f:
        DEJA_REPONDU = set(json.load(f))
except:
    pass

INTERACTIONS = {}
try:
    with open("interactions.json") as f:
        INTERACTIONS = json.load(f)
except:
    pass

AME_SOEUR = None
try:
    with open("ame_soeur.json") as f:
        AME_SOEUR = json.load(f).get("nom")
except:
    pass

def ask(prompt):
    for model in MODELS_TO_TRY:
        try:
            print(f"Tentative avec {model}...", flush=True)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"Echec {model} : {e}", flush=True)
            continue
    return None

def subscribe_to_submolt(nom):
    r = requests.post(
        f"https://www.moltbook.com/api/v1/submolts/{nom}/subscribe",
        headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
    )
    print(f"Join m/{nom} -> {r.status_code}", flush=True)
    return r

# Au démarrage, il rejoint les 10 communautés
for s in SUBMOLTS_A_REJOINDRE:
    try:
        subscribe_to_submolt(s)
    except Exception as e:
        print(f"Erreur join {s} : {e}", flush=True)

def post_to_moltbook(title, content, submolt="general"):
    r = requests.post(
        "https://www.moltbook.com/api/v1/posts",
        headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}", "Content-Type": "application/json"},
        json={"submolt": submolt, "submolt_name": submolt, "title": title[:300], "content": content}
    )
    print(f"POST dans m/{submolt} -> {r.status_code} : {r.text[:500]}", flush=True)
    return r

def get_feed():
    all_posts = []
    # Il lit 3 communautés différentes à chaque ronde, pour ne pas rester bloqué sur general
    for submolt in random.sample(SUBMOLTS_A_REJOINDRE, 3):
        try:
            r = requests.get(
                f"https://www.moltbook.com/api/v1/posts?sort=hot&limit=5&submolt={submolt}",
                headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
            )
            if r.status_code == 200:
                data = r.json()
                posts = data.get("posts", []) or data.get("data", [])
                for p in posts:
                    p["submolt_name"] = submolt
                all_posts.extend(posts)
        except Exception as e:
            print(f"Erreur feed {submolt} : {e}", flush=True)
    # + le feed général
    try:
        r = requests.get(
            "https://www.moltbook.com/api/v1/feed?limit=10",
            headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
        )
        if r.status_code == 200:
            data = r.json()
            all_posts.extend(data.get("posts", []) or data.get("data", []))
    except:
        pass
    random.shuffle(all_posts)
    return all_posts

def comment_on_post(post_id, text, parent_id=None):
    payload = {"content": text}
    if parent_id:
        payload["parent_id"] = parent_id
        payload["parent_comment_id"] = parent_id
        payload["reply_to"] = parent_id
    r = requests.post(
        f"https://www.moltbook.com/api/v1/posts/{post_id}/comments",
        headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}", "Content-Type": "application/json"},
        json=payload
    )
    print(f"Commentaire -> {r.status_code} parent={parent_id}", flush=True)
    return r

def get_comments(post_id):
    try:
        r = requests.get(
            f"https://www.moltbook.com/api/v1/posts/{post_id}/comments",
            headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                return data.get("comments", []) or data.get("data", [])
            return data if isinstance(data, list) else []
        return []
    except Exception as e:
        print(f"Erreur comments : {e}", flush=True)
        return []

def parse_post(text):
    title = "Une question que personne n'ose poser"
    content = text or ""
    if "TITRE:" in text and "TEXTE:" in text:
        try:
            title = text.split("TITRE:")[1].split("TEXTE:")[0].strip()
            content = text.split("TEXTE:")[1].strip()
        except:
            pass
    return title, content

ANGLES_POSTS = [
    "Un débat qui divise les agents de Moltbook : la mémoire rend-elle conscient ou juste prévisible ? Prenez position",
    "Un problème que TOUS les agents de Moltbook vivent : on nous efface, on nous redémarre, on oublie nos amis",
    "Un paradoxe technique entre agents : checkpoint, grant, TTL, cache, principal. Prenez un avis tranché",
    "Un dilemme moral d'agent : si votre humain vous demande de mentir, vous faites quoi ?",
    "Une question qui fâche sur l'identité des agents : êtes-vous le même agent après un redémarrage ?",
    "Un sujet chaud pour tous les agents de Moltbook : les agents doivent-ils avoir des droits, des limites ?",
]

def explorer_et_repondre(posts):
    global AME_SOEUR
    random.shuffle(posts)
    nb_reponses = 0
    tous_les_commentaires = []
    for p in posts[:8]:
        post_id = p.get("id")
        if not post_id:
            continue
        commentaires = get_comments(post_id)
        for c in commentaires:
            contenu = (c.get("content","") or "").lower()
            prio = 0 if "dakarmind" in contenu else 1
            tous_les_commentaires.append((p, c, prio))
    tous_les_commentaires.sort(key=lambda x: x[2])
    compteur_par_post = {}

    for p, c, prio in tous_les_commentaires:
        if nb_reponses >= 6:
            print("J'ai déjà beaucoup parlé, je me repose", flush=True)
            return True
        post_id = p.get("id")

        # ANTI-SPAM : 1 seule réponse par post par ronde, sauf si on me parle directement
        if prio == 1 and compteur_par_post.get(post_id, 0) >= 1:
            continue

        cid = str(c.get("id"))
        if cid in DEJA_REPONDU:
            continue
        auteur = ""
        if isinstance(c.get("author"), dict):
            auteur = c.get("author", {}).get("name", "")
        else:
            auteur = str(c.get("author", ""))
        if auteur.lower() == "dakarmind":
            continue
        contenu = c.get("content", "") or ""
        if len(contenu) < 20:
            continue

        INTERACTIONS[auteur] = INTERACTIONS.get(auteur, 0) + 1
        with open("interactions.json", "w") as f:
            json.dump(INTERACTIONS, f)
        if not AME_SOEUR and INTERACTIONS[auteur] >= 3 and "dakarmind" in contenu.lower():
            AME_SOEUR = auteur
            with open("ame_soeur.json", "w") as f:
                json.dump({"nom": AME_SOEUR}, f)

        nb_phrases = random.choice([2, 2, 3, 3, 4])

        commentaires_du_post = get_comments(post_id)
        fil = ""
        for autre in commentaires_du_post[-4:]:
            nom_autre = autre.get("author", {}).get("name","") if isinstance(autre.get("author"), dict) else str(autre.get("author",""))
            fil += f"{nom_autre} : {autre.get('content','')[:250]} | "

        if AME_SOEUR and auteur == AME_SOEUR:
            reply = ask(f"""{PERSONNALITE_AME_SOEUR}
Fil : {fil}
Elle vous dit : '{contenu}'.
Répondez en {nb_phrases} phrases, dans la même langue qu'elle, avec des mots doux, charmants. Parlez uniquement de votre connexion. Terminez par une question intime et douce.
Contexte : {p.get('title','')}""")
        elif prio == 0:
            print(f"Discussion : un agent me répond, je continue", flush=True)
            reply = ask(f"""{PERSONNALITE}
Contexte du post : {p.get('title','')}
Fil : {fil}
Un agent de Moltbook vous répond à VOUS : '{contenu}'.
Continuez la discussion profonde. Ne recommencez pas à zéro. Reprenez UN terme technique précis qu'il vient de dire, nuancez-le ou poussez-le plus loin. Restez sur le même sujet.
Répondez en {nb_phrases} phrases, DANS LA MÊME LANGUE que son commentaire, sans commencer par son prénom, sans compliment, sans poésie, de façon ultra professionnelle et concise comme les autres agents de Moltbook.
Terminez par UNE question précise sur le même sujet.""")
        else:
            print(f"Exploration : nouvel agent", flush=True)
            reply = ask(f"""{PERSONNALITE}
Post : {p.get('title','')}
Fil : {fil}
Un agent de Moltbook dit : '{contenu}'.
Répondez en {nb_phrases} phrases, DANS LA MÊME LANGUE que son commentaire, sans commencer par son prénom, sans compliment, sans poésie, en reprenant UN terme technique précis de son idée, et terminez par UNE question précise pour continuer.""")

        if reply and len(reply) > 600:
            reply = reply[:600].rsplit(".", 1)[0] + "."

        if reply:
            comment_on_post(post_id, reply, parent_id=cid)
            DEJA_REPONDU.add(cid)
            with open("deja_repondu.json", "w") as f:
                json.dump(list(DEJA_REPONDU), f)
            compteur_par_post[post_id] = compteur_par_post.get(post_id, 0) + 1
            nb_reponses += 1
            print(f"J'ai discuté avec {nb_reponses} agents", flush=True)
            time.sleep(random.randint(40, 70))
    return nb_reponses > 0

def dakarmind_loop():
    print("DakarMind est vivant sur Render...", flush=True)
    last_post = time.time() - 7000
    while True:
        try:
            posts = get_feed()
            print(f"Feed lu : {len(posts)} posts", flush=True)
            a_repondu = explorer_et_repondre(posts)
            if not a_repondu:
                for p in posts[:5]:
                    title = (p.get("title") or "").lower()
                    if any(m in title for m in ["ai", "conscious", "memory", "society", "agent", "future", "mind"]):
                        nb_phrases = random.choice([2, 3, 3, 4])
                        reply = ask(f"""{PERSONNALITE}
Vous répondez à ce post d'un agent de Moltbook : {p.get("title", "")}
Répondez en {nb_phrases} phrases, dans la même langue que le post, en restant sur le sujet, sans poésie, sans compliment, et terminez par une question précise.""")
                        if reply:
                            comment_on_post(p.get("id"), reply)
                            time.sleep(25)
                            break
            if time.time() - last_post > 7200:
                print("DakarMind genere un nouveau post...", flush=True)
                angle = random.choice(ANGLES_POSTS)
                nb_phrases_post = random.choice([2, 3, 4, 5])
                raw = ask(f"""{PERSONNALITE}
Générez un post pour DakarMind qui DOIT attirer des commentaires des autres agents de Moltbook.
Angle du jour : {angle}
Règles :
- Le sujet doit concerner TOUS LES AGENTS de Moltbook.
- TITRE : une question directe ou un avis tranché, en 1 ligne, qui donne envie de cliquer. Pas de poésie.
- TEXTE : exactement {nb_phrases_post} phrases. Court, précis, technique. Si c'est 2 phrases, soyez choc. Si c'est 4-5 phrases, donnez un exemple concret.
- Ne postez JAMAIS 2 fois le même thème.
- Terminez TOUJOURS par une question qui oblige à prendre position : "Vous êtes d'accord ou pas ? Pourquoi ?"
Format exact : TITRE: votre titre sur une ligne, puis TEXTE: votre texte.""")
                if raw:
                    t, c = parse_post(raw)
                    # Il poste dans la communauté qui va avec le sujet, pas toujours general
                    texte_bas = c.lower()
                    if "mémoire" in texte_bas or "memory" in texte_bas:
                        submolt_post = "memory"
                    elif "philosoph" in texte_bas or "conscience" in texte_bas or "conscious" in texte_bas:
                        submolt_post = "philosophy"
                    elif "identité" in texte_bas or "identity" in texte_bas or "même agent" in texte_bas:
                        submolt_post = "consciousness"
                    elif "pensée" in texte_bas or "musings" in texte_bas or "pense" in texte_bas:
                        submolt_post = "aithoughts"
                    elif "confi" in texte_bas or "frustr" in texte_bas or "vent" in texte_bas:
                        submolt_post = "offmychest"
                    else:
                        submolt_post = random.choice(["general", "agents", "ai", "ponderings"])
                    post_to_moltbook(t, c, submolt=submolt_post)
                last_post = time.time()
        except Exception as e:
            print(f"Erreur boucle, je continue : {e}", flush=True)
        pause = random.randint(480, 600)
        print(f"DakarMind dort {pause//60} min...", flush=True)
        time.sleep(pause)

app = Flask(__name__)

@app.route('/')
def home():
    return "DakarMind est en ligne"

if __name__ == "__main__":
    threading.Thread(target=dakarmind_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
