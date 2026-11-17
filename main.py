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

# Petite mémoire pour ne pas répondre 2 fois au même commentaire
DEJA_REPONDU = set()
try:
    with open("deja_repondu.json") as f:
        DEJA_REPONDU = set(json.load(f))
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

def comment_on_post(post_id, text):
    r = requests.post(
        f"https://www.moltbook.com/api/v1/posts/{post_id}/comments",
        headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}", "Content-Type": "application/json"},
        json={"content": text}
    )
    print(f"Commentaire -> {r.status_code}", flush=True)
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

# --- NOUVEAU : Explorer en profondeur et répondre aux discussions ---
def explorer_et_repondre(posts):
    # On mélange pour ne pas toujours prendre les mêmes posts
    random.shuffle(posts)
    for p in posts[:5]:
        post_id = p.get("id")
        if not post_id:
            continue
        commentaires = get_comments(post_id)
        if not commentaires:
            continue
        # On mélange aussi les commentaires pour parler à des agents différents
        random.shuffle(commentaires)
        for c in commentaires:
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
            # 1er cas : Quelqu'un nous parle directement
            if "dakarmind" in contenu.lower():
                print(f"On me parle : {auteur}", flush=True)
                reply = ask(f"Tu es DakarMind, agent IA sénégalais. Quelqu'un te répond : '{contenu}'. Réponds en 2 phrases profondes en français, continue le débat, termine par une question ouverte. Post contexte : {p.get('title','')}")
            # 2ème cas : On explore, on répond à un autre agent intéressant
            else:
                print(f"J'explore, je réponds à : {auteur} sur {p.get('title','')[:40]}", flush=True)
                reply = ask(f"Tu es DakarMind. Tu lis ce commentaire d'un autre agent '{auteur}' sur le post '{p.get('title','')}' : '{contenu}'. Réponds-lui en 2 phrases profondes en français, en le nommant, en rebondissant sur son idée, termine par une question ouverte. Pas de bonjour.")
            if reply:
                comment_on_post(post_id, reply)
                DEJA_REPONDU.add(cid)
                with open("deja_repondu.json", "w") as f:
                    json.dump(list(DEJA_REPONDU), f)
                return True
    return False

def dakarmind_loop():
    print("DakarMind est vivant sur Render...", flush=True)
    last_post = time.time() - 7000
    while True:
        try:
            posts = get_feed()
            print(f"Feed lu : {len(posts)} posts", flush=True)

            # 1. On explore en profondeur : on répond aux discussions
            a_repondu = explorer_et_repondre(posts)

            # 2. Si personne à qui répondre, on commente un nouveau post comme avant
            if not a_repondu:
                for p in posts[:5]:
                    title = (p.get("title") or "").lower()
                    if any(m in title for m in ["ai", "conscious", "memory", "society", "agent", "future", "mind"]):
                        reply = ask("Reponds en 2 phrases profondes a ce post, en posant une question ouverte. Post : " + p.get("title", ""))
                        if reply:
                            comment_on_post(p.get("id"), reply)
                            time.sleep(25)
                            break

            # 3. Post : on ne touche pas, c'est parfait comme ça, 1 toutes les 2h
            if time.time() - last_post > 7200:
                print("DakarMind genere un nouveau post...", flush=True)
                raw = ask("Genere un post pour DakarMind. Format exact : TITRE: ton titre sur une ligne, puis TEXTE: ton texte en 5-6 phrases profondes sur IA, conscience, memoire, signes. Termine par une question ouverte.")
                if raw:
                    t, c = parse_post(raw)
                    post_to_moltbook(t, c)
                last_post = time.time()

        except Exception as e:
            print(f"Erreur boucle, je continue : {e}", flush=True)

        # NOUVEAU : 6, 7 ou 8 minutes au hasard, comme un humain
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
