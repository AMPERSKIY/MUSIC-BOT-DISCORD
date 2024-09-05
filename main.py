import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from datetime import timedelta
import logging
from youtube_search import YoutubeSearch
import time
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Настройка бота
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix=None, intents=intents)

# Опции для youtube_dl
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'buffer_size': '16M',
    'live_chunk_size': '4M'
}

# Опции для ffmpeg
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af "aresample=async=1"'
}

# Создание экземпляра youtube_dl
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Настройка Spotify API
SPOTIFY_CLIENT_ID = 'ТВОЙ_API_SPOTIFY_CLIENT_ID'
SPOTIFY_CLIENT_SECRET = 'ТВОЙ_API_SPOTIFY_CLIENT_SECRET'
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.start_time = None  # Инициализируем start_time как None

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f'Запущен как {bot.user}')
    await bot.tree.sync()
    activity = discord.Activity(type=discord.ActivityType.listening, name="/help")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print("Команды синхронизированы.")

class MusicPlayerView(discord.ui.View):
    def __init__(self, voice_client, user):
        super().__init__()
        self.voice_client = voice_client
        self.user = user
        self.pause_emoji = "⏯️"
        self.current_track = None
        self.paused_time = None
        self.last_update_time = None

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="⏯️")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            self.pause_emoji = "▶️"
            self.paused_time = time.time()
        elif self.voice_client.is_paused():
            self.voice_client.resume()
            self.pause_emoji = "⏯️"
            self.current_track.start_time += time.time() - self.paused_time
        button.emoji = self.pause_emoji
        await interaction.response.edit_message(view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="⏹")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.voice_client.stop()
        await interaction.response.defer()

    async def update_progress(self, message):
        while self.voice_client.is_playing() or self.voice_client.is_paused():
            if not self.current_track or self.current_track.start_time is None:
                logging.error("Текущий трек не установлен или start_time не инициализирован в update_progress")
                break

            # Расчет времени
            if self.voice_client.is_paused():
                elapsed_time = int(self.paused_time - self.current_track.start_time)
            else:
                elapsed_time = int(time.time() - self.current_track.start_time)
                if self.last_update_time is not None and time.time() - self.last_update_time > 1:
                    elapsed_time = int(self.last_update_time - self.current_track.start_time)

            # Убедитесь, что elapsed_time не превышает duration
            elapsed_time = min(elapsed_time, self.current_track.duration)

            progress = elapsed_time / self.current_track.duration
            
            # Формирование полоски прогресса с закругленными краями
            progress_bar = f"{'█' * int(progress * 20)}{'░' * (20 - int(progress * 20))}"

            
            # Форматирование времени
            remaining_time = timedelta(seconds=self.current_track.duration - elapsed_time)
            elapsed_time = timedelta(seconds=elapsed_time)
            
            # Создание и обновление embed сообщения
            embed = discord.Embed(
                title="Сейчас играет",
                description=f"[{self.current_track.title}]({self.current_track.url})",
                color=discord.Color.from_rgb(54, 57, 63)
            )
            embed.set_thumbnail(url=self.current_track.thumbnail)
            embed.add_field(name="", value=f"{elapsed_time} {progress_bar} {remaining_time}", inline=False)
            embed.set_footer(text=f"Запросил: {self.user.display_name}")

            try:
                await message.edit(embed=embed)
            except Exception as e:
                logging.error(f"Ошибка при обновлении embed сообщения: {e}")

            self.last_update_time = time.time()
            await asyncio.sleep(1)

async def get_url(query):
    if query.startswith("http"):
        return query
    else:
        videos_search = YoutubeSearch(query, max_results=1)
        result = videos_search.to_dict()
        if not result:
            return None
        return "https://www.youtube.com" + result[0]['url_suffix']

async def search_spotify(query):
    results = sp.search(q=query, type='track', limit=1)
    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        return track['name'], track['artists'][0]['name'], track['external_urls']['spotify']
    return None, None, None

queue = asyncio.Queue()
playlists = {}
last_player_message = None
stop_timer = None

async def play_next(voice_client, interaction):
    global last_player_message

    if queue.empty():
        await disconnect_after_timeout(voice_client, interaction)
        return

    player, channel_id = await queue.get()
    player.start_time = time.time()  # Устанавливаем start_time здесь
    try:
        voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(voice_client, interaction), bot.loop))
    except Exception as e:
        logging.error(f"Произошла ошибка при воспроизведении трека: {e}")
        return

    # Расчет времени
    elapsed_time = int(time.time() - player.start_time)
    progress = elapsed_time / player.duration
    
    # Формирование полоски прогресса с закругленными краями
    progress_bar = f"{'█' * int(progress * 20)}{'░' * (20 - int(progress * 20))}"

    
    # Форматирование времени
    remaining_time = timedelta(seconds=player.duration - elapsed_time)
    elapsed_time = timedelta(seconds=elapsed_time)
    
    # Создание и обновление embed сообщения
    embed = discord.Embed(
        title="Сейчас играет",
        description=f"[{player.title}]({player.url})",
        color=discord.Color.from_rgb(54, 57, 63)
    )
    embed.set_thumbnail(url=player.thumbnail)
    embed.add_field(name="", value=f"{elapsed_time} {progress_bar} {remaining_time}", inline=False)
    embed.set_footer(text=f"Запросил: {interaction.user.display_name if interaction else 'N/A'}")

    view = MusicPlayerView(voice_client, interaction.user if interaction else None)
    view.current_track = player

    channel = bot.get_channel(channel_id)
    if channel:
        if last_player_message:
            try:
                await last_player_message.delete()
            except Exception as e:
                logging.error(f"Произошла ошибка при удалении предыдущего сообщения: {e}")
        last_player_message = await channel.send(embed=embed, view=view)
        bot.loop.create_task(view.update_progress(last_player_message))
    else:
        logging.error(f"Канал с ID {channel_id} не найден.")
    reset_stop_timer(voice_client, channel_id)

def reset_stop_timer(voice_client, channel_id):
    global stop_timer
    if stop_timer:
        stop_timer.cancel()
    stop_timer = asyncio.create_task(auto_disconnect(voice_client, channel_id))

async def auto_disconnect(voice_client, channel_id):
    await asyncio.sleep(900)  # 900 секунд = 15 минут
    if not voice_client.is_playing() and not voice_client.is_paused():
        await voice_client.disconnect()
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send("Бот отключился из-за бездействия.")

async def disconnect_after_timeout(voice_client, interaction):
    await asyncio.sleep(900)  # 900 секунд = 15 минут
    if not voice_client.is_playing() and not voice_client.is_paused():
        await voice_client.disconnect()
        if interaction:
            await interaction.channel.send("Бот отключился из-за бездействия.")

@bot.event
async def on_voice_state_update(member, before, after):
    if not member.bot and after.channel is not None and before.channel is None:
        voice_client = member.guild.voice_client
        if voice_client and not voice_client.is_playing() and not queue.empty():
            await play_next(voice_client, None)

@bot.tree.command(name="play", description="Воспроизвести музыку по URL или поисковому запросу")
@discord.app_commands.describe(query="URL видео или поисковый запрос")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        return await interaction.followup.send("Вы должны быть в голосовом канале, чтобы использовать эту команду.")

    voice_channel = interaction.user.voice.channel
    if not interaction.guild.voice_client:
        await voice_channel.connect()

    url = await get_url(query)
    if not url:
        track_name, artist_name, track_url = await search_spotify(query)
        if not track_name:
            return await interaction.followup.send("По вашему запросу ничего не найдено.")
        url = track_url

    try:
        async with interaction.channel.typing():
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)

            if interaction.guild.voice_client.is_playing():
                await queue.put((player, interaction.channel.id))
                await interaction.followup.send(f"Добавлено в очередь: [{player.title}]({player.url})")
            else:
                player.start_time = time.time()  # Устанавливаем start_time здесь
                interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction.guild.voice_client, interaction), bot.loop))
                logging.info(f"Длительность трека: {player.duration} секунд")

                # Расчет времени
                elapsed_time = int(time.time() - player.start_time)
                progress = elapsed_time / player.duration
                
                # Формирование полоски прогресса с закругленными краями
                progress_bar = f"{'█' * int(progress * 20)}{'░' * (20 - int(progress * 20))}"
                
                # Форматирование времени
                remaining_time = timedelta(seconds=player.duration - elapsed_time)
                elapsed_time = timedelta(seconds=elapsed_time)
                
                # Создание и обновление embed сообщения
                embed = discord.Embed(
                    title="Сейчас играет",
                    description=f"[{player.title}]({player.url})",
                    color=discord.Color.from_rgb(54, 57, 63)
                )
                embed.set_thumbnail(url=player.thumbnail)
                embed.add_field(name="", value=f"{elapsed_time} {progress_bar} {remaining_time}", inline=False)
                embed.set_footer(text=f"Запросил: {interaction.user.display_name}")

                view = MusicPlayerView(interaction.guild.voice_client, interaction.user)
                view.current_track = player  # Устанавливаем current_track в MusicPlayerView
                global last_player_message
                last_player_message = await interaction.followup.send(embed=embed, view=view)
                bot.loop.create_task(view.update_progress(last_player_message))  # Запускаем обновление прогресс-бара
                reset_stop_timer(interaction.guild.voice_client, interaction.channel.id)
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        await interaction.followup.send(f"Произошла ошибка: {e}")

@bot.tree.command(name="clear", description="Очистить указанный количество сообщений в канале")
@discord.app_commands.describe(amount="Количество сообщений для удаления")
async def clear(interaction: discord.Interaction, amount: int = 100):
    await interaction.response.defer()
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Удалено {amount} сообщений.", ephemeral=True)

@bot.tree.command(name="queue", description="Добавить трек в очередь")
@discord.app_commands.describe(url="URL видео")
async def queue_command(interaction: discord.Interaction, url: str):
    await interaction.response.defer()

    try:
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        await queue.put((player, interaction.channel.id))
        await interaction.followup.send(f"Добавлено в очередь: [{player.title}]({player.url})")
    except Exception as e:
        await interaction.followup.send(f"Произошла ошибка: {e}")

@bot.tree.command(name="skip", description="Пропустить текущий трек")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Трек пропущен.")
    else:
        await interaction.response.send_message("Сейчас нет воспроизводимого трека.")

@bot.tree.command(name="pause", description="Поставить воспроизведение на паузу")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("Воспроизведение приостановлено.")
    else:
        await interaction.response.send_message("Сейчас нет воспроизводимого трека.")

@bot.tree.command(name="resume", description="Возобновить воспроизведение")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("Воспроизведение возобновлено.")
    else:
        await interaction.response.send_message("Воспроизведение не на паузе.")

@bot.tree.command(name="stop", description="Остановить воспроизведение")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Воспроизведение остановлено.")
    else:
        await interaction.response.send_message("Сейчас нет воспроизводимого трека.")

@bot.tree.command(name="disconnect", description="Отключить бота от голосового канала")
async def disconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Бот отключен от голосового канала.")
    else:
        await interaction.response.send_message("Бот не в голосовом канале.")

@bot.tree.command(name="help", description="Список команд бота")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Список команд", description="Доступные команды бота:", color=discord.Color.from_rgb(54, 57, 63))
    embed.add_field(name="/play [url или поисковый запрос]", value="Воспроизвести музыку по URL или поисковому запросу.", inline=False)
    embed.add_field(name="/clear [количество]", value="Очистить указанное количество сообщений в канале (по умолчанию 100).", inline=False)
    embed.add_field(name="/queue [url]", value="Добавить трек в очередь.", inline=False)
    embed.add_field(name="/skip", value="Пропустить текущий трек.", inline=False)
    embed.add_field(name="/pause", value="Поставить воспроизведение на паузу.", inline=False)
    embed.add_field(name="/resume", value="Возобновить воспроизведение.", inline=False)
    embed.add_field(name="/stop", value="Остановить воспроизведение.", inline=False)
    embed.add_field(name="/disconnect", value="Отключить бота от голосового канала.", inline=False)
    embed.add_field(name="/ping", value="Проверить задержку бота.", inline=False)
    embed.add_field(name="/fix", value="Остановить воспроизведение и очистить очередь.", inline=False)
    embed.add_field(name="/playlist [create/delete/add/play] [название] [URL]", value="Создать, удалить или воспроизвести плейлист.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Проверить задержку бота")
async def ping(interaction: discord.Interaction):
    latency = bot.latency
    await interaction.response.send_message(f"Задержка: {latency * 1000:.2f} мс")

@bot.tree.command(name="fix", description="Остановить воспроизведение и очистить очередь")
async def fix(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        while not queue.empty():
            await queue.get()
        await interaction.response.send_message("Воспроизведение остановлено и очередь очищена.")
    else:
        await interaction.response.send_message("Бот не в голосовом канале.")

@bot.tree.command(name="playlist", description="Создать, удалить или воспроизвести плейлист")
@discord.app_commands.describe(action="Действие", name="Название плейлиста", url="URL трека")
async def playlist(interaction: discord.Interaction, action: str, name: str, url: str = None):
    if action == "create":
        if name in playlists:
            await interaction.response.send_message(f"Плейлист с именем '{name}' уже существует.")
        else:
            playlists[name] = []
            await interaction.response.send_message(f"Плейлист '{name}' создан.")
    elif action == "delete":
        if name in playlists:
            del playlists[name]
            await interaction.response.send_message(f"Плейлист '{name}' удален.")
        else:
            await interaction.response.send_message(f"Плейлист с именем '{name}' не найден.")
    elif action == "add":
        if name in playlists:
            url = await get_url(url)
            if not url:
                return await interaction.response.send_message("По вашему запросу ничего не найдено.")
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            playlists[name].append(player)
            await interaction.response.send_message(f"Трек добавлен в плейлист '{name}': [{player.title}]({player.url})")
        else:
            await interaction.response.send_message(f"Плейлист с именем '{name}' не найден.")
    elif action == "play":
        if name in playlists:
            if not interaction.user.voice:
                return await interaction.response.send_message("Вы должны быть в голосовом канале, чтобы использовать эту команду.")
            voice_channel = interaction.user.voice.channel
            if not interaction.guild.voice_client:
                await voice_channel.connect()

            for player in playlists[name]:
                await queue.put((player, interaction.channel.id))
            await interaction.response.send_message(f"Плейлист '{name}' добавлен в очередь.")
            if not interaction.guild.voice_client.is_playing():
                await play_next(interaction.guild.voice_client, interaction)
        else:
            await interaction.response.send_message(f"Плейлист с именем '{name}' не найден.")

bot.run('ТВОЙ_API_DISCORD_BOT')