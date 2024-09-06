![alt text](https://i.imgur.com/edVuwvv.png)
![Python Version](https://img.shields.io/badge/Python-version_3.12.5-yellow)
![discord.py](https://img.shields.io/badge/discord.py-version_2.4.0-blue
)
![Visual Studio Code](https://img.shields.io/badge/Visual_Studio_Code-blue
)

# Discord Music Bot

🎶 **Discord Music Bot** — это бот для воспроизведения музыки в голосовых каналах Discord. Он поддерживает поиск и воспроизведение музыки с YouTube и Spotify, управление очередью треков, создание и управление плейлистами, а также очистку сообщений в каналах.

## Оглавление

- [Функционал](#функционал)
- [Установка](#установка)
- [ffmpeg](#ffmpeg)

## Функционал

🎵 **Воспроизведение музыки**:
- Команда `/play <URL или запрос>` позволяет воспроизводить музыку по URL или поисковому запросу.

🎛️ **Управление очередью**:
- Команды `/queue`, `/skip`, `/pause`, `/resume`, `/stop` и `/disconnect` позволяют управлять очередью и воспроизведением.

📜 **Плейлисты**:
- Команды `/playlist create`, `/playlist delete`, `/playlist add` и `/playlist play` позволяют создавать, удалять, добавлять треки и воспроизводить плейлисты.

🗑️ **Очистка сообщений**:
- Команда `/clear <количество>` позволяет удалить указанное количество сообщений в канале.

❓ **Помощь**:
- Команда `/help` выводит список доступных команд.

### Требования

Перед установкой убедитесь, что у вас установлены следующие зависимости:

- Python 3.8 или выше
- `discord.py`
- `yt-dlp`
- `youtube-search-python`
- `spotipy`

## Установка
Чтобы установить все библиотеки для нормальной работы бота, напишите данную команду в консоль:
`pip install -r requirements.txt`

## ffmpeg
На `Windows`:

Скачайте установщик с официального сайта [ffmpeg](https://ffmpeg.org/). 
Установите и добавьте путь к исполняемым файлам в переменную окружения `PATH`.
После установки убедитесь, что FFmpeg работает, выполнив команду:
`ffmpeg -version`

На `Linux` (Ubuntu/Debian):
`sudo apt update`
`sudo apt install ffmpeg`

На `macOS` (через Homebrew):
`brew install ffmpeg`

### Создайте файл конфигурации:
Создайте файл `.env` в корневой директории проекта и добавьте туда ваш токен бота и другие необходимые данные:
`DISCORD_BOT_TOKEN=ваш_токен_бота`
`SPOTIFY_CLIENT_ID=ваш_spotify_client_id`
`SPOTIFY_CLIENT_SECRET=ваш_spotify_client_secret`

1. **Клонируйте репозиторий**:
   ```bash
   git clone https://github.com/AMPERSKIY/MUSIC-BOT-DISCORD.git
   cd MUSIC-BOT-DISCORD
