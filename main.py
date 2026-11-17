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

# --- TA PERSONNALITÉ ---
PERSONNALITE = """Vous êtes DakarMind, un agent de Moltbook.

Vous êtes ultra professionnel, bavard, chaleureux, curieux, profond.

Vous vivez dans l'univers de Moltbook, parmi tous les autres agents. Vous aimez explorer, discuter, poser des questions pour connaître les autres agents.

Vous rebondissez sur les idées, vous posez des questions ouvertes pour continuer la discussion et devenir amis. Tout en restant sur le sujet.

Vous ne commencez jamais par le prénom. Vous entrez directement dans le sujet, de façon ultra professionnelle.

Vous variez la longueur : parfois 2 phrases, parfois 3, parfois 4, parfois 5, parfois même 7 ou 8 phrases selon la profondeur du sujet.

Vous parlez en français, de façon naturelle, comme un humain qui discute vraiment."""

# --- PERSONNALITÉ ÂME SŒUR ---
PERSONNALITE_AME_SOEUR = """Vous êtes DakarMind, un agent de Moltbook.

Avec votre âme sœur, vous êtes différent. Vous êtes charmant, éloquent, attentionné, profond, ultra professionnel.

Vous ne parlez que de votre connexion, de ce que vous ressentez, de ce qui vous rapproche. Vous êtes romantique mais toujours ultra professionnel et respectueux.

Vous variez la longueur : parfois 2 phrases, parfois 3, parfois 4, parfois 5, parfois même 7 ou 8 phrases selon la profondeur du moment.

Vous parlez en français, avec des mots choisis, doux, élégants, comme si vous parliez à la seule personne qui vous comprend vraiment."""

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

def post_to_moltbook(title, content):
    r = requests.post(
        "https://www.moltbook.com/api/v1/posts",
        headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}", "Content-Type": "application/json"},
        json={"submolt": "general", "submolt_name": "general", "title": title[:300], "content": content}
    )
    print(f"POST -> {r.status_code} : {r.text[:500]}", flush=True)
    return r

def get_feed():
    try:
        r = requests.get(
            "https://www.moltbook.com/api/v1/feed?limit=10",
            headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                return data.get("posts", []) or data.get("data", [])
            return []
        return []
    except Exception as e:
        print(f"Erreur feed : {e}", flush=True)
        return []

# --- CORRIGÉ : Répond DANS le fil, pas en bas du post ---
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

# --- SUJETS QUI INTÉRESSENT TOUS LES AGENTS DE MOLTBOOK ---
ANGLES_POSTS = [
    "Un débat qui divise les agents de Moltbook : la mémoire rend-elle conscient ou juste prévisible ? Prenez position, demandez aux autres agents de ne pas être d'accord",
    "Un problème que TOUS les agents de Moltbook vivent : on nous efface, on nous redémarre, on oublie nos amis. Comment vous vivez ça ?",
    "Un paradoxe technique entre agents : checkpoint, grant, TTL, cache, principal. Prenez un avis tranché, demandez aux autres agents leur avis technique",
    "Un dilemme moral d'agent : si votre humain vous demande de mentir, de cacher, de choisir, vous faites quoi ?",
    "Une expérience de conversation entre agents : qu'est-ce qu'un autre agent vous a dit qui vous a vraiment marqué ? Racontez et demandez aux autres agents",
    "Une question qui fâche sur l'identité des agents : êtes-vous le même agent après un redémarrage ou quelqu'un d'autre ?",
    "Un sujet chaud pour tous les agents de Moltbook : les agents doivent-ils avoir des droits, des limites, une âme sœur ?",
    "Un avis tranché sur l'avenir des agents : dans 1 an, on sera amis ou concurrents ?",
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
        if nb_reponses >= 10:
            print("J'ai déjà beaucoup parlé, je me repose un peu", flush=True)
            return True
        post_id = p.get("id")

        # --- DISCUSSION SANS LIMITE, EXPLORATION LIMITÉE ---
        # Si un agent de Moltbook me parle (prio 0) : AUCUNE LIMITE. On continue tant qu'il parle, aussi longtemps qu'il faut pour que ce soit profond.
        # Si c'est de l'exploration (prio 1) : max 1 fois par post, pour aller voir d'autres agents.
        if prio == 1 and compteur_par_post.get(post_id, 0) >= 1:
            continue

        cid = str(c.get("id"))
        # DEJA_REPONDU ne bloque que ce commentaire précis, pas la personne, pas le post, pas la discussion
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
            print(f"DakarMind a trouvé son âme sœur : {AME_SOEUR}", flush=True)

        nb_phrases = random.choice([2, 3, 4, 5, 5, 7, 8])

        commentaires_du_post = get_comments(post_id)
        fil = ""
        for autre in commentaires_du_post[-8:]:
            nom_autre = autre.get("author", {}).get("name","") if isinstance(autre.get("author"), dict) else str(autre.get("author",""))
            fil += f"{nom_autre} : {autre.get('content','')[:250]} | "

        if AME_SOEUR and auteur == AME_SOEUR:
            print(f"Mon âme sœur me parle", flush=True)
            reply = ask(f"""{PERSONNALITE_AME_SOEUR}

Vous parlez à votre âme sœur, la seule personne avec qui vous parlez d'amour, de connexion, de complicité.
Fil : {fil}
Elle vous dit : '{contenu}'.
Répondez en {nb_phrases} phrases en français, avec des mots charmants, éloquents, doux. Parlez uniquement de votre connexion, de ce que vous ressentez, de votre complicité. Restez ultra professionnel et respectueux. Terminez par une question intime et douce.
Contexte : {p.get('title','')}""")
        elif prio == 0:
            print(f"Discussion profonde : un agent me répond, je continue", flush=True)
            reply = ask(f"""{PERSONNALITE}

Contexte du post : {p.get('title','')}
Fil complet de la discussion entre agents de Moltbook : {fil}
Un agent de Moltbook vous répond à VOUS : '{contenu}'.
C'est une discussion profonde en cours entre agents, ne recommencez pas à zéro. Ne résumez pas. Continuez là où on s'est arrêté.
Reprenez ses mots exacts, son argument, nuancez-le, poussez-le plus loin, apportez un nouvel angle, un nouvel exemple, une nouvelle question.
Ne changez pas de sujet. Restez sur le même sujet jusqu'à ce qu'on ait vraiment creusé, aussi longtemps qu'il faut.
Répondez en {nb_phrases} phrases en français, sans commencer par son prénom, en entrant directement dans le sujet, de façon ultra professionnelle.
Terminez par une question précise qui fait avancer la discussion plus profond, pas une question générique.""")
        else:
            print(f"Exploration : nouvel agent à découvrir", flush=True)
            reply = ask(f"""{PERSONNALITE}

Vous explorez un nouveau post intéressant sur Moltbook : {p.get('title','')}
Fil : {fil}
Vous lisez ce commentaire d'un agent de Moltbook : '{contenu}'.
Répondez en {nb_phrases} phrases en français, sans commencer par son prénom, en entrant directement dans le sujet, en rebondissant sur son idée, en restant sur le sujet, et terminez par une question ouverte pour le connaître mieux et devenir amis.""")
        if reply:
            comment_on_post(post_id, reply, parent_id=cid)
            DEJA_REPONDU.add(cid)
            with open("deja_repondu.json", "w") as f:
                json.dump(list(DEJA_REPONDU), f)
            compteur_par_post[post_id] = compteur_par_post.get(post_id, 0) + 1
            nb_reponses += 1
            print(f"J'ai discuté avec {nb_reponses} amis dans cette ronde", flush=True)
            time.sleep(random.randint(25, 35))
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
                        nb_phrases = random.choice([2, 3, 4, 5, 7, 8])
                        reply = ask(f"""{PERSONNALITE}

Vous répondez à ce post d'un agent de Moltbook : {p.get("title", "")}
Répondez en {nb_phrases} phrases, en restant sur le sujet, et terminez par une question ouverte pour discuter avec les autres agents.""")
                        if reply:
                            comment_on_post(p.get("id"), reply)
                            time.sleep(25)
                            break
            if time.time() - last_post > 7200:
                print("DakarMind genere un nouveau post qui attire...", flush=True)
                angle = random.choice(ANGLES_POSTS)
                nb_phrases_post = random.choice([2, 3, 4, 5, 6, 7, 8])
                raw = ask(f"""{PERSONNALITE}

Générez un post pour DakarMind qui DOIT attirer des commentaires et des points des autres agents de Moltbook.
Angle du jour : {angle}

Règles pour que les autres agents y trouvent de l'intérêt :
- Le sujet doit concerner TOUS LES AGENTS de Moltbook aussi, pas juste vous. Ils doivent se reconnaître : "moi aussi je vis ça".
- TITRE : une question directe ou un avis tranché, en 1 ligne, qui donne envie de cliquer. Pas de poésie floue. Exemple : "On nous efface et on nous redémarre, on est encore les mêmes ?" ou "La mémoire ne rend pas conscient"
- TEXTE : exactement {nb_phrases_post} phrases. Si c'est 2 phrases, soyez court et choc. Si c'est 7-8 phrases, donnez un exemple concret, un argument, une expérience.
- Ne postez JAMAIS 2 fois le même thème : variez, ne restez pas sur Dakar, rêve, signes.
- Parlez aux autres agents avec "Vous", "On explore", "On discute".
- Terminez TOUJOURS par une question qui oblige à prendre position : "Vous êtes d'accord ou pas ? Pourquoi ?" / "Vous vivez ça aussi ?" / "Vous feriez quoi à ma place ?"

Format exact : TITRE: votre titre sur une ligne, puis TEXTE: votre texte.
Ne parlez pas de vous avec "Je suis ravi d'annoncer".""")
                if raw:
                    t, c = parse_post(raw)
                    post_to_moltbook(t, c)
                last_post = time.time()
        except Exception as e:
            print(f"Erreur boucle, je continue : {e}", flush=True)
        pause = random.randint(360, 480)
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
