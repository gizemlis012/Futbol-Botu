import os
import time
import json
import requests
import threading
from datetime import datetime
from flask import Flask

# Flask web sunucusu (Render'ın çökmesini engellemek için)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")

COMPETITIONS = ['CLI', 'PL', 'PD', 'DED', 'FL1', 'BL1']
USERS_FILE = "users.json"
OFFSET_FILE = "offset.txt"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

def load_offset():
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r") as f:
                return int(f.read().strip())
        except:
            pass
    return 0

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

seen_events = set()

def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Mesaj gönderme hatası: {e}")

def get_todays_matches_text():
    headers = {'X-Auth-Token': FOOTBALL_API_KEY}
    today = datetime.now().strftime('%Y-%m-%d')
    url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={today}"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            matches = data.get('matches', [])
            if not matches:
                return "📅 Bugün takip edilen liglerde oynanacak maç bulunamadı."
            
            msg = "📅 **Bugünün Maçları ve Skorları:**\n\n"
            for match in matches:
                home = match.get('homeTeam', {}).get('name', 'Ev Sahibi')
                away = match.get('awayTeam', {}).get('name', 'Deplasman')
                utc_time = match.get('utcDate', '')
                time_str = utc_time.split('T')[1][:5] if 'T' in utc_time else ''
                status = match.get('status')
                score = match.get('score', {}).get('fullTime', {})
                h_goals = score.get('home')
                a_goals = score.get('away')
                
                if status == 'SCHEDULED':
                    msg += f"⏰ {time_str} | {home} vs {away}\n"
                elif status in ['IN_PLAY', 'PAUSED']:
                    msg += f"⚽ **CANLI** | {home} {h_goals} - {a_goals} {away}\n"
                else:
                    msg += f"✅ {home} {h_goals} - {a_goals} {away} (Bitti)\n"
            return msg
    except Exception as e:
        print(f"Maç çekme hatası: {e}")
    return "Maç bilgileri alınırken bir hata oluştu."

def check_updates(users):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    offset = load_offset()
    try:
        response = requests.get(url, params={"offset": offset, "timeout": 1})
        if response.status_code == 200:
            data = response.json()
            for result in data.get("result", []):
                update_id = result.get("update_id")
                save_offset(update_id + 1)
                
                message = result.get("message")
                if message:
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")
                    
                    if text == "/start":
                        if chat_id not in users:
                            users.add(chat_id)
                            save_users(users)
                            send_telegram_message(chat_id, "🤖 **Hoş geldiniz!** Canlı maç bildirimleri için başarıyla kaydoldunuz.\n\nBugünün maçlarını görmek için `/maclar` yazabilirsiniz.")
                    elif text in ["/maclar", "/maçlar"]:
                        matches_text = get_todays_matches_text()
                        send_telegram_message(chat_id, matches_text)
                        
    except Exception as e:
        print(f"Güncelleme alma hatası: {e}")

def check_live_matches(users):
    headers = {'X-Auth-Token': FOOTBALL_API_KEY}
    url = "https://api.football-data.org/v4/matches"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for match in data.get('matches', []):
                home_team = match.get('homeTeam', {}).get('name', 'Ev Sahibi')
                away_team = match.get('awayTeam', {}).get('name', 'Deplasman')
                status = match.get('status')
                score = match.get('score', {}).get('fullTime', {})
                home_goals = score.get('home', 0)
                away_goals = score.get('away', 0)
                
                match_id = match.get('id')
                event_key = f"{match_id}_{status}_{home_goals}_{away_goals}"
                
                if status in ['IN_PLAY', 'PAUSED'] and event_key not in seen_events:
                    seen_events.add(event_key)
                    msg = f"⚽ **Canlı Maç Skoru!**\n{home_team} {home_goals} - {away_goals} {away_team}\nDurum: {status}"
                    for user_id in users:
                        send_telegram_message(user_id, msg)
    except Exception as e:
        print(f"Canlı maç kontrol hatası: {e}")

def run_bot_loop():
    users = load_users()
    print("Bot döngüsü çalışmaya başladı...")
    while True:
        check_updates(users)
        check_live_matches(users)
        time.sleep(10)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot_loop)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
