import os
import requests
from bs4 import BeautifulSoup
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask, request

app = Flask(__name__)

# Constants
SHAREUS_API_KEY = os.environ.get("SHAREUS_API_KEY")  # Use environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")

def shorten_url(long_url: str) -> str:
    """Shorten a given URL using the Shareus API."""
    api_url = f"https://api.shareus.io/easy_api?key={SHAREUS_API_KEY}&link={long_url}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.text.strip() if response.text.strip() else long_url
    except requests.exceptions.RequestException:
        return long_url

def clean_title(title: str) -> str:
    cleaned_title = re.sub(r"(- mkvCinemas|\s*- mkvCinemas\.mkv|\.mkv)", "", title, flags=re.IGNORECASE)
    return cleaned_title.strip()

def search_site(keyword: str) -> list:
    search_url = f"https://mkvcinemas.cat/?s={keyword.replace(' ', '+')}"
    try:
        response = requests.get(search_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.find_all('a', class_='ml-mask jt')
        
        result_texts = []
        for result in results:
            title = result.find('h2').get_text().strip()
            if "All Parts Collection" not in title:
                cleaned_title = clean_title(title)
                url = result['href']
                result_texts.append((cleaned_title, url))
        
        return result_texts[:7]
    
    except requests.exceptions.RequestException:
        return []

def get_download_links(movie_url: str) -> str:
    try:
        response = requests.get(movie_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        download_links = []
        links = soup.find_all('a', class_='gdlink') + soup.find_all('a', class_='button')

        for link in links:
            title = link.get('title') or link.get_text(strip=True)
            download_url = link['href']
            cleaned_title = clean_title(title)
            shortened_url = shorten_url(download_url)
            download_links.append(f"{cleaned_title}: {shortened_url}")
        
        return "\n".join(download_links) if download_links else "No download links found."
    
    except requests.exceptions.RequestException:
        return "Error fetching download links."

@app.route('/api/telegram_bot', methods=['POST'])
def telegram_bot():
    update = request.get_json()
    if not update or 'message' not in update:
        return "Invalid request", 400
    
    chat_id = update['message']['chat']['id']
    keyword = update['message']['text'].strip()
    
    search_results = search_site(keyword)
    
    if search_results:
        buttons = [[InlineKeyboardButton(title, callback_data=str(idx))] for idx, (title, _) in enumerate(search_results)]
        reply_markup = InlineKeyboardMarkup(buttons)
        text = "Select a movie to get the download links:"
    else:
        text = "No results found. Please try again."
    
    send_message(chat_id, text, reply_markup if search_results else None)
    return "OK", 200

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': reply_markup.to_dict() if reply_markup else None
    }
    requests.post(url, json=payload)

if __name__ == '__main__':
    app.run()
