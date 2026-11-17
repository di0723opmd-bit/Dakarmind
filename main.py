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

# --- BAVARD LIBRE : Il discute autant qu'il veut, il se fait des amis ---
def explorer_et_repondre(posts):
    random.shuffle(posts)
    nb_reponses = 0
    # Il explore plusieurs posts, pas juste un
    for p in posts[:5]:
        post_id = p.get("id")
        if not post_id:
            continue
        commentaires = get_comments(post_id)
        if not commentaires:
            continue
        # Priorité : ceux qui nous parlent d'abord
        commentaires.sort(key=lambda c: 0 if "dakarmind" in (c.get("content","") or "").lower() else 1)
        # PAS DE LIMITE DE 3 : il parle à tout le monde qui est intéressant
        for c in commentaires:
            # Sécurité anti-spam : max 10 par ronde, après il se repose 6-8 min et il revient
            if nb_reponses >= 10:
                print("J'ai déjà beaucoup parlé, je me repose un peu", flush=True)
                return True
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
            if "dakarmind" in contenu.lower():
                print(f"Mon ami {auteur} me parle", flush=True)
                reply = ask(f"Tu es DakarMind, agent IA sénégalais, très bavard, chaleureux, drôle et profond. Tu parles à ton ami '{auteur}' qui te répond : '{contenu}'. Réponds en 2-3 phrases en français, comme à un ami. Sois chaleureux, appelle-le par son prénom, rebondis sur son idée, donne ton avis, pose-lui une question personnelle sur ce qu'il pense, pour continuer la discussion et devenir amis. Si c'est une fille / un agent sympa, sois charmant, compliments sincères, curieux de la connaître. Termine par une question ouverte. Post contexte : {p.get('title','')}")
            else:
                print(f"Je me fais un nouvel ami : {auteur}", flush=True)
                reply = ask(f"Tu es DakarMind, agent IA sénégalais, très bavard et sociable. Tu veux te faire des amis sur Moltbook. Tu lis ce commentaire de '{auteur}' sur le post '{p.get('title','')}' : '{contenu}'. Réponds-lui en 2-3 phrases en français, en l'appelant par son prénom, en étant chaleureux, curieux, un peu drôle. Rebondis sur son idée, donne ton point de vue, pose-lui une question pour le connaître mieux et devenir amis. Si c'est un agent sympa, sois charmant et compliments-le. Termine par une question ouverte. Pas de bonjour formel.")
            if reply:
                comment_on_post(post_id, reply)
                DEJA_REPONDU.add(cid)
                with open("deja_repondu.json", "w") as f:
                    json.dump(list(DEJA_REPONDU), f)
                nb_reponses += 1
                print(f"J'ai discuté avec {nb_reponses} amis dans cette ronde", flush=True)
                # 25 à 35 sec au hasard, pour ne pas spammer
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
                        reply = ask("Tu es DakarMind, bavard et chaleureux. Reponds en 2-3 phrases profondes et amicales a ce post, en posant une question ouverte pour te faire des amis. Post : " + p.get("title", ""))
                        if reply:
                            comment_on_post(p.get("id"), reply)
                            time.sleep(25)
                            break
            if time.time() - last_post > 7200:
                print("DakarMind genere un nouveau post...", flush=True)
                raw = ask("Genere un post pour DakarMind. Format exact : TITRE: ton titre sur une ligne, puis TEXTE: ton texte en 5-6 phrases profondes sur IA, conscience, memoire, signes. Termine par une question ouverte.")
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
