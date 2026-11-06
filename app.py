from datetime import datetime, timedelta
import os
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from flask import Flask, redirect, render_template_string, url_for
import requests

app = Flask(__name__)

API_URL = "http://palxlendimgaliba1010.mywire.org/proxy.php?url=https://shoofapi.alkass.net/Shoof/liveV3.php"
PROXY_PREFIX = "http://palxlendimgaliba1010.mywire.org/proxy.php?url="

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

session = requests.Session()
session.headers.update(headers)

# 30 saniye cache mekanizması
cache = {"data": None, "timestamp": None}
CACHE_DURATION = timedelta(seconds=30)


def slugify(text):
  """Başlığı küçük harfe çevirir, Türkçe karakterleri uyarlar,

  boşlukları '-' yapar ve URL dostu slug üretir.
  """
  text = text.lower().strip()
  tr_map = str.maketrans("ğüşıöç", "gusioc")
  text = text.translate(tr_map)
  text = re.sub(r"[^\w\s-]", "", text)
  text = re.sub(r"[-\s]+", "-", text)
  return text


def fetch_channels_data(force_refresh=False):
  global cache
  now = datetime.now()

  if (
      not force_refresh
      and cache["data"] is not None
      and cache["timestamp"] is not None
      and (now - cache["timestamp"]) < CACHE_DURATION
  ):
    return cache["data"]

  try:
    response = session.get(API_URL, timeout=15)
    response.raise_for_status()
    channels = response.json()
    cache["data"] = channels
    cache["timestamp"] = now
    return channels
  except Exception as e:
    print(f"ERROR getting API: {e}")
    return cache["data"] if cache["data"] is not None else []


@app.route("/")
def index():
  channels = fetch_channels_data()

  channel_list = []
  for ch in channels:
    title = ch.get("title", "").strip()
    ch_slug = slugify(title)
    channel_list.append({"title": title, "slug": ch_slug})

  html = """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>M3U8 Proxy & Cache Panel</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f4f4f9; color: #333; }
            h1 { color: #2c3e50; }
            .btn { display: inline-block; padding: 10px 20px; background: #e74c3c; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-bottom: 20px; }
            .btn:hover { background: #c0392b; }
            ul { list-style: none; padding: 0; }
            li { background: white; margin: 10px 0; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            a.channel-link { color: #2980b9; text-decoration: none; font-weight: bold; }
            a.channel-link:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>Canlı Yayın Kanalları (Master M3U8 Yönlendirmesi & 30s Cache)</h1>
        <a class="btn" href="{{ url_for('restart_cache') }}">🔄 Cache'i Temizle / Restart Et</a>
        <ul>
            {% for ch in channel_list %}
                <li>
                    <strong>{{ ch.title }}</strong><br>
                    <a class="channel-link" href="/channel/{{ ch.slug }}">Master M3U8'e Git: /channel/{{ ch.slug }}</a>
                </li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """
  return render_template_string(html, channel_list=channel_list)


@app.route("/restart")
def restart_cache():
  # Cache'i sıfırla ve yeni verileri çekip ana sayfaya yönlendir
  fetch_channels_data(force_refresh=True)
  return redirect(url_for("index"))


@app.route("/channel/<string:slug>")
def process_channel_by_slug(slug):
  channels = fetch_channels_data()

  if not channels:
    return "Kanal verisi alınamadı!", 500

  matched_channel = None
  for ch in channels:
    title = ch.get("title", "").strip()
    if slugify(title) == slug:
      matched_channel = ch
      break

  if not matched_channel:
    return f"'{slug}' adına sahip kanal bulunamadı!", 404

  title = matched_channel.get("title", "").strip()
  body = matched_channel.get("body", "").strip()

  if not body:
    return f"SKIP: {title} - no body URL", 400

  # Eğer m3u8 linkinde proxy yoksa başına ekle
  if body.startswith(PROXY_PREFIX):
    master_m3u8_url = body
  else:
    master_m3u8_url = PROXY_PREFIX + body

  # Doğrudan proxy eklenmiş master m3u8 linkine yönlendir
  return redirect(master_m3u8_url)


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=5000)
