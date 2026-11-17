"""DakarMind v2 : agent Moltbook sur la mémoire des agents.

Changements majeurs par rapport à la version Copilot :
- résolution des défis de vérification Moltbook (sans ça, le contenu reste non publié)
- POST en un seul essai, jamais rejoué (Moltbook crée le contenu avant la vérification)
- gestion du 429 / Retry-After
- état persistant dans STATE_DIR (monter un disque Render dessus, sinon l'état se perd)
- plus de double commentaire sur un même post
- consigne système séparée, texte externe balisé contre les injections
- filtre qualité aligné sur la persona, sans troncature qui coupe la question finale
"""
import difflib
import json
import logging
import os
import random
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask
from openai import OpenAI


# -------------------- Configuration --------------------

MOLTBOOK_API_KEY = os.getenv("MOLTBOOK_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

AGENT_NAME = "DakarMind"
# Garde le "www" : sans lui, l'en-tête Authorization peut être perdu à la redirection.
MOLTBOOK_URL = "https://www.moltbook.com/api/v1"

MODELS_TO_TRY = [
    "openrouter/free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "baidu/ernie-5.5-flash-preview:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
]
