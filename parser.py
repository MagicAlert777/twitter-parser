import asyncio
import aiohttp
from bs4 import BeautifulSoup
import os
import json
import random
from itertools import cycle
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Список инстанций Nitter
NITTER_INSTANCES = [
    "https://xcancel.com",
    "https://nitter.space",
    "nitter.privacydev.net",
]
nitter_pool = cycle(NITTER_INSTANCES)

# Список прокси (можно оставить пустым, так как GitHub Actions использует разные IP)
PROXIES = [
    None,  # Без прокси, так как GitHub Actions предоставляет разные IP
]
proxy_pool = cycle(PROXIES)

# Список User-Agent
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
]
user_agent_pool = cycle(USER_AGENTS)

# Получаем профили из переменной окружения
GROUP_INDEX = int(os.getenv("GROUP_INDEX", "0"))
PROFILES = ["holley_mar73454"] * 20  # 20 профилей на группу, замените на свои
last_tweets = {profile: None for profile in PROFILES}

# Функция для парсинга твита
def parse_tweet(html):
    soup = BeautifulSoup(html, 'lxml')
    tweet = soup.find('div', class_='timeline-item')
    if not tweet:
        return None

    tweet_link = tweet.find('a', class_='tweet-link')
    if not tweet_link or 'href' not in tweet_link.attrs:
        return None

    tweet_id = tweet_link['href'].split('/')[-1].split('#')[0]
    tweet_text = tweet.find('div', class_='tweet-content').text.strip() if tweet.find('div', class_='tweet-content') else "Текст не найден"
    return {"tweet_id": tweet_id, "text": tweet_text}

# Функция для проверки профиля
async def check_profile(session, username, instance, proxy, user_agent, attempt=1):
    url = f"{instance}/{username}"
    logging.info(f"Проверка профиля {username} через {instance} (попытка {attempt}/3)...")
    try:
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        async with session.get(url, headers=headers, proxy=proxy, timeout=15) as response:
            if response.status == 403:
                if attempt < 3:
                    logging.info("Повторная попытка с новым прокси и инстанцией через 5 секунд...")
                    await asyncio.sleep(5)
                    new_proxy = next(proxy_pool)
                    new_instance = next(nitter_pool)
                    new_user_agent = next(user_agent_pool)
                    return await check_profile(session, username, new_instance, new_proxy, new_user_agent, attempt + 1)
                return None

            if response.status != 200:
                return None

            html = await response.text()
            tweet_data = parse_tweet(html)
            if not tweet_data:
                return None

            tweet_data["username"] = username
            return tweet_data

    except Exception as e:
        logging.error(f"Ошибка для {username}: {str(e)}")
        return None

# Функция для обработки профиля
async def process_profile(session, username):
    global last_tweets

    instance = next(nitter_pool)
    proxy = next(proxy_pool)
    user_agent = next(user_agent_pool)
    tweet_data = await check_profile(session, username, instance, proxy, user_agent)
    if not tweet_data:
        return None

    tweet_id = tweet_data["tweet_id"]
    if last_tweets[username] is None or last_tweets[username]["tweet_id"] != tweet_id:
        last_tweets[username] = tweet_data
        logging.info(f"Новый твит для {username}: {tweet_data['text']}")
        return tweet_data
    return None

# Основной цикл
async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [process_profile(session, username) for username in PROFILES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        with open(f"results_group_{GROUP_INDEX}.json", "w") as f:
            json.dump([r for r in results if r], f)

if __name__ == "__main__":
    asyncio.run(main())
