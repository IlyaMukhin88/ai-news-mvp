import feedparser
import requests
import yaml
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- RSS ----------
def collect_news(sources, limit):
    news = []
    for url in sources:
        feed = feedparser.parse(url)
        for e in feed.entries[:limit]:
            news.append({
                "title": e.title,
                "summary": e.get("summary", ""),
                "source": feed.feed.get("title", "Unknown")
            })
    return news


# ---------- FREE LLM (HuggingFace) ----------
def generate_text(news):
    prompt = f"""
Ты финансовый новостной редактор.
Сделай краткий новостной выпуск (3–5 минут).
Без прогнозов и советов.
Только факты.

Новости:
{news}
"""

    r = requests.post(
        "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
        headers={"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"},
        json={"inputs": prompt, "parameters": {"max_new_tokens": 700}}
    )
    return r.json()[0]["generated_text"]


# ---------- SLIDES ----------
def make_slide(text, idx):
    img = Image.new("RGB", (1280, 720), (20, 20, 30))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((50, 50), text[:900], fill="white", font=font)
    path = f"{OUTPUT_DIR}/slide_{idx}.png"
    img.save(path)
    return path


# ---------- TTS ----------
def make_audio(text):
    tts = gTTS(text=text, lang="ru")
    path = f"{OUTPUT_DIR}/audio.mp3"
    tts.save(path)
    return path


# ---------- VIDEO ----------
def make_video(slide, audio):
    out = f"{OUTPUT_DIR}/video.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", slide,
        "-i", audio,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-shortest",
        "-pix_fmt", "yuv420p",
        out
    ])
    return out


# ---------- TELEGRAM ----------
def send_telegram(text, video):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text[:4000]}
    )

    with open(video, "rb") as v:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendVideo",
            data={"chat_id": chat_id},
            files={"video": v}
        )


# ---------- MAIN ----------
def main():
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    news = collect_news(cfg["rss_sources"], cfg["max_news"])
    text = generate_text(news)

    slide = make_slide(text, 0)
    audio = make_audio(text)
    video = make_video(slide, audio)

    if cfg["telegram"]["enabled"]:
        send_telegram(text, video)

    print("DONE")


if __name__ == "__main__":
    main()

