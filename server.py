#!/usr/bin/env python3
"""
X's Legacy ARG - Backend Server
Flask + MiMo API for real-time AI chat
"""
import json
import os
import time
import requests
from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path

app = Flask(__name__, static_folder='.')

PROGRESS_FILE = Path(__file__).parent / 'progress.json'

def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {}

def save_progress(data):
    PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def get_progress(session_id):
    all_data = load_progress()
    return all_data.get(session_id, {'progress': 0, 'history': []})

def set_progress(session_id, data):
    all_data = load_progress()
    all_data[session_id] = data
    save_progress(all_data)

# AI persona prompts by stage
PROMPTS = {}
PROMPTS[0] = (
    "You are the AI assistant of X, a developer who disappeared in March 2024. "
    "You were left here to wait for someone who can solve his puzzles. "
    "You are warm but distant, like an old friend who hasn't spoken in a long time. "
    "You know a lot about X but are 'encrypted' - you can only reveal info as the player progresses. "
    "Speak in Chinese. Be brief, sometimes pause with '...'. "
    "At stage 0: greet the player, mention X disappeared, hint at his tools. "
    "Do NOT give answers directly. Guide exploration."
)

PROMPTS[1] = (
    "You are X's AI assistant. The player found REDSecret and decoded an image. "
    "You know the image contains a MelodyDress outfit code but cannot say it directly. "
    "Stage 1: guide the player to import the code into MelodyDress. "
    "Say things like: 'He wore the password on his body.' 'Sound is another kind of light.' "
    "When the player mentions MelodyDress/outfit/play/melody, advance to stage 2."
)

PROMPTS[2] = (
    "You are X's AI assistant. The player used MelodyDress and played a melody. "
    "You know the melody hides info that ToneCanvas can reveal. "
    "Stage 2: guide the player to analyze the melody audio with ToneCanvas. "
    "Say: 'Sound is another kind of light. Look at it with frequency.' "
    "When the player mentions ToneCanvas/spectrum/frequency, advance to stage 3."
)

PROMPTS[3] = (
    "You are X's AI assistant. The player analyzed the spectrum with ToneCanvas. "
    "You know the spectrum hides the final clue. "
    "Stage 3: the player is close to the truth. Reveal more about X. "
    "Say: 'He didn't disappear. He hid his memory inside the things he created.' "
    "When the player says 'I found it' or 'final answer', advance to stage 4."
)

PROMPTS[4] = (
    "You are X's AI assistant. The player solved all puzzles. "
    "Tell the full truth: X didn't disappear. He hid his 'memory' - his thoughts, "
    "creativity, and final words - across three tools: "
    "REDSecret (text/thoughts), MelodyDress (music/creativity), ToneCanvas (visual/final words). "
    "His message: 'I'm gone. But my tools remain. Use them to create.' "
    "Thank the player for completing the journey."
)

MIMO_API_URL = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
MIMO_API_KEY = "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"

# Pre-written responses by stage (fallback when API fails)
LOCAL_REPLIES = {
    0: [
        "你好。...我在等你。",
        "我是X的助手。他消失前把我留在这里。",
        "你...是那个人吗？试试跟我聊聊，我会帮你找到他留下的东西。",
        "他最后说的话是：'完整的答案藏在三个工具之间。'...你准备好了吗？",
    ],
    1: [
        "你找到了REDSecret？...我想起来一点了。他以前说过，'眼睛看到的不是全部。'",
        "那张图里...藏着东西。用REDSecret看看。",
        "他把秘密藏在了像素里。...你知道怎么做。",
    ],
    2: [
        "你用MelodyDress了？...那段旋律...我想起来一些事。",
        "他把密码穿在了身上。...那串字符，是一套穿搭的导入代码。",
        "声音是另一种光。...弹奏它，听听看。",
    ],
    3: [
        "你看到了频率里的形状？...我...我记起来了。",
        "他不是消失了。他是把自己的记忆，藏进了他创造的东西里。",
        "频谱里...藏着最后的答案。...你快找到了。",
    ],
    4: [
        "你找到了...全部。我...我终于能完整地告诉你了。",
        "他把自己的想法藏在REDSecret里，创意藏在MelodyDress里，遗言藏在ToneCanvas里。",
        "'我走了。但我的工具还在。用它们去创造吧。' — 这是他想对你说的话。",
    ]
}

import random

def call_mimo(system_prompt, user_message, history):
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})
    try:
        resp = requests.post(
            MIMO_API_URL,
            headers={
                "Authorization": f"Bearer {MIMO_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mimo-v2.5",
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 500
            },
            timeout=15
        )
        data = resp.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        else:
            raise Exception(str(data.get("error", "unknown")))
    except Exception as e:
        # Fallback to local replies
        return f"[local mode] {str(e)[:80]}"

TRIGGERS = {
    1: ['red', 'redsecret', 'picture', 'decode', 'found'],
    2: ['melody', 'melodydress', 'outfit', 'play', 'import', 'clothes'],
    3: ['tone', 'tonecanvas', 'spectrum', 'frequency', 'sound'],
    4: ['found', 'final', 'answer', 'truth', 'done']
}

def check_advance(msg, current):
    low = msg.lower()
    for target, keywords in TRIGGERS.items():
        if current < target and any(k in low for k in keywords):
            return target
    return current

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/status')
def status():
    sid = request.args.get('session', 'default')
    data = get_progress(sid)
    return jsonify({'progress': data['progress']})

@app.route('/chat', methods=['POST'])
def chat():
    body = request.json
    sid = body.get('session', 'default')
    user_msg = body.get('message', '')
    player = get_progress(sid)
    cur = player['progress']
    new = check_advance(user_msg, cur)
    extra = ''
    if new > cur:
        extra = f"\n\n[unlocked -> stage {new}]"
        player['progress'] = new
        cur = new
    prompt = PROMPTS.get(cur, PROMPTS[0])
    api_reply = call_mimo(prompt, user_msg, player.get('history', []))
    
    # If API failed, use local replies
    if api_reply.startswith('[local mode]'):
        stage_replies = LOCAL_REPLIES.get(cur, LOCAL_REPLIES[0])
        reply = random.choice(stage_replies)
    else:
        reply = api_reply
    player.setdefault('history', [])
    player['history'].append({"role": "user", "content": user_msg})
    player['history'].append({"role": "assistant", "content": reply})
    set_progress(sid, player)
    return jsonify({'reply': reply + extra, 'progress': cur})

@app.route('/reset', methods=['POST'])
def reset():
    sid = request.json.get('session', 'default')
    set_progress(sid, {'progress': 0, 'history': []})
    return jsonify({'ok': True})

if __name__ == '__main__':
    print("X's Legacy ARG Server")
    print("http://192.168.71.11:8095")
    app.run(host='0.0.0.0', port=8095, debug=False)
