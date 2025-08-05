from flask import Flask, request, render_template, jsonify
import threading
import cloudscraper
import websocket
import json
import os
import redis

app = Flask(__name__)

redis_url = os.environ.get("REDIS_URL")
rdb = redis.from_url(redis_url)

kick_slug = 'sampanday'

def get_chatroom_id(slug):
    endpoint = f"https://kick.com/api/v2/channels/{slug}"
    scraper = cloudscraper.create_scraper()
    r = scraper.get(endpoint)
    data = r.json()
    chatroom_id = data.get("chatroom_id")
    if not chatroom_id and "chatroom" in data:
        chatroom_id = data["chatroom"].get("id")
    return chatroom_id

def listen_to_kick_chat(chatroom_id):
    def on_message(ws, message):
        try:
            data = json.loads(message)
            if data.get("event") == "App\\Events\\ChatMessageEvent":
                msg = json.loads(data["data"])
                content = msg.get("content")
                badges = msg.get("sender", {}).get("identity", {}).get("badges", [])
                badge_types = [badge.get("type") for badge in badges]
                name = msg.get("sender", {}).get("username", "Unknown")
                if 'broadcaster' in badge_types or 'moderator' in badge_types or name == 'Zam_LIVE':
                    if content.startswith('!drinks'):
                        if content == '!drinks delete':
                            rdb.set("drinks", 0)
                            print(f'command received: {content} (new total: {0})')
                            return
                        drinks = content.split('!drinks')[1].strip()
                        try:
                            add_value = int(drinks)
                        except ValueError:
                            print(f"Invalid drink value: {drinks}")
                            return
                        rdb.set("drinks", add_value)
                        print(f'command received: {content} (new total: {add_value})')
        except Exception as e:
            print("Error:", e)

    def on_open(ws):
        ws.send(json.dumps({
            "event": "pusher:subscribe",
            "data": {
                "auth": "",
                "channel": f"chatrooms.{chatroom_id}.v2"
            }
        }))

    ws = websocket.WebSocketApp(
        "wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=js&version=8.4.0-rc2&flash=false",
        on_open=on_open,
        on_message=on_message
    )
    ws.run_forever()

chatroom_id = get_chatroom_id(kick_slug)
# Start the chat listener in a background thread
threading.Thread(target=listen_to_kick_chat, args=(chatroom_id,), daemon=True).start()

@app.route('/')
def index():
    return render_template('overlay.html')

@app.route('/drinks')
def get_drinks():
    value = rdb.get("drinks")
    drinks = int(value) if value else 0
    return jsonify({'drinks': drinks})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)