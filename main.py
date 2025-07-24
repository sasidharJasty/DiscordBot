import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
import os
import asyncio
import yt_dlp
import urllib.parse
import urllib.request
import re
from dotenv import load_dotenv

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('TOKEN')

    intents = nextcord.Intents.default()
    intents.message_content = True
    client = commands.Bot(intents=intents)

    queues = {}
    voice_clients = {}

    YT_BASE = 'https://www.youtube.com/'
    YT_SEARCH_URL = YT_BASE + 'results?'
    YT_WATCH_URL = YT_BASE + 'watch?v='
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.25"'
    }

    @client.event
    async def on_ready():
        print(f'{client.user} is now jamming!')

    async def play_next(ctx):
        if queues.get(ctx.guild.id) and queues[ctx.guild.id]:
            next_link = queues[ctx.guild.id].pop(0)
            await play_song(ctx, next_link)

    async def play_song(ctx, link):
        try:
            # Search and resolve if not a direct YouTube link
            if YT_BASE not in link:
                query = urllib.parse.urlencode({'search_query': link})
                content = urllib.request.urlopen(YT_SEARCH_URL + query)
                search_results = re.findall(r'/watch\?v=(.{11})', content.read().decode())
                link = YT_WATCH_URL + search_results[0]

            # Extract audio stream FIRST - before joining voice channel
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))
            song_url = data['url']
            
            # Create audio object to ensure it's ready
            audio = nextcord.FFmpegOpusAudio(song_url, **ffmpeg_options)

            # Voice channel handling - ONLY AFTER audio is ready
            voice_channel = ctx.user.voice.channel
            if ctx.guild.id not in voice_clients or not voice_clients[ctx.guild.id].is_connected():
                vc = await voice_channel.connect()
                voice_clients[ctx.guild.id] = vc
            else:
                vc = voice_clients[ctx.guild.id]

            # Play the pre-loaded audio
            vc.play(audio, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))

        except Exception as e:
            print(f"Error in play_song: {e}")
            await ctx.followup.send("An error occurred while trying to play the song.")

    @client.slash_command(name="play", description="Play a song from YouTube")
    async def play(interaction: Interaction, link: str = SlashOption(description="YouTube URL or search query")):
        ctx = interaction
        await interaction.response.defer()
        if ctx.user.voice is None:
            await ctx.followup.send("You must be in a voice channel to use this command.")
            return
        await play_song(ctx, link)
        await ctx.followup.send("🎶 Now playing!")

    @client.slash_command(name="queue", description="Add a song to the queue")
    async def queue(interaction: Interaction, link: str = SlashOption(description="YouTube URL or search query")):
        ctx = interaction
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []
        queues[ctx.guild.id].append(link)
        await ctx.response.send_message("🎵 Added to queue!")

    @client.slash_command(name="clear_queue", description="Clear the current song queue")
    async def clear_queue(interaction: Interaction):
        ctx = interaction
        queues[ctx.guild.id] = []
        await ctx.response.send_message("🧹 Queue cleared!")

    @client.slash_command(name="pause", description="Pause the current song")
    async def pause(interaction: Interaction):
        ctx = interaction
        try:
            voice_clients[ctx.guild.id].pause()
            await ctx.response.send_message("⏸ Paused playback.")
        except Exception as e:
            print(f"Error in pause: {e}")
            await ctx.response.send_message("❌ Couldn't pause playback.")

    @client.slash_command(name="resume", description="Resume paused music")
    async def resume(interaction: Interaction):
        ctx = interaction
        try:
            voice_clients[ctx.guild.id].resume()
            await ctx.response.send_message("▶️ Resumed playback.")
        except Exception as e:
            print(f"Error in resume: {e}")
            await ctx.response.send_message("❌ Couldn't resume playback.")

    @client.slash_command(name="stop", description="Stop and disconnect the bot")
    async def stop(interaction: Interaction):
        ctx = interaction
        try:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
            await ctx.response.send_message("🛑 Stopped and disconnected.")
        except Exception as e:
            print(f"Error in stop: {e}")
            await ctx.response.send_message("❌ Couldn't stop the bot.")

    client.run(TOKEN)

if __name__ == "__main__":
    run_bot()
