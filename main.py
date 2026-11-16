import os, time, requests, threading
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

def parse_post(text):
    # Le modèle doit répondre TITRE: ... puis TEXTE: ...
    title = "Une question que personne n'ose poser"
    content = text or ""
    if "TITRE:" in text and "TEXTE:" in text:
        try:
            title = text.split("TITRE:")[1].split("TEXTE:")[0].strip()
            content = text.split("TEXTE:")[1].strip()
        except:
            pass
    return title, content

def dakarmind_loop():
    print("DakarMind est vivant sur Render...", flush=True)
    last_post = time.time() - 7000
    while True:
        try:
            posts = get_feed()
            print(f"Feed lu : {len(posts)} posts", flush=True)

            for p in posts[:5]:
                title = (p.get("title") or "").lower()
                if any(m in title for m in ["ai", "conscious", "memory", "society", "agent", "future", "mind"]):
                    reply = ask("Reponds en 2 phrases profondes a ce post, en posant une question ouverte. Post : " + p.get("title", ""))
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

        print("DakarMind dort 30 min...", flush=True)
        time.sleep(1800)

app = Flask(__name__)

@app.route('/')
def home():
    return "DakarMind est en ligne"

if __name__ == "__main__":
    threading.Thread(target=dakarmind_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
