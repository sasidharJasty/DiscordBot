import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import urllib.parse
import urllib.request
import re

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('TOKEN')

    intents = nextcord.Intents.default()
    intents.message_content = True
    client = commands.Bot(intents=intents)

    queues = {}
    voice_clients = {}
    youtube_base_url = 'https://www.youtube.com/'
    youtube_results_url = youtube_base_url + 'results?'
    youtube_watch_url = youtube_base_url + 'watch?v='
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.25"'
    }

    @client.event
    async def on_ready():
        print(f'{client.user} is now jamming')

    async def play_next(ctx):
        if queues.get(ctx.guild.id):
            if queues[ctx.guild.id] != []:
                link = queues[ctx.guild.id].pop(0)
                await play(ctx, link=link)

    @client.slash_command(name="play", description="Play a YouTube song")
    async def play(interaction: Interaction, link: str = SlashOption(description="YouTube URL or search term")):
        ctx = interaction
        await interaction.response.defer()

        try:
            if ctx.user.voice is None:
                await ctx.followup.send("You must be in a voice channel to play music.")
                return

            # First resolve the actual YouTube link
            if youtube_base_url not in link:
                query_string = urllib.parse.urlencode({'search_query': link})
                content = urllib.request.urlopen(youtube_results_url + query_string)
                search_results = re.findall(r'/watch\?v=(.{11})', content.read().decode())
                link = youtube_watch_url + search_results[0]

            # Download video info BEFORE joining VC
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))
            song = data['url']

            # Now join the VC
            voice_channel = ctx.user.voice.channel
            if ctx.guild.id not in voice_clients or not voice_clients[ctx.guild.id].is_connected():
                voice_client = await voice_channel.connect()
                voice_clients[ctx.guild.id] = voice_client
            else:
                voice_client = voice_clients[ctx.guild.id]

            # Finally play the audio
            player = nextcord.FFmpegOpusAudio(song, **ffmpeg_options)
            voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
            await ctx.followup.send("🎶 Now playing!")

        except Exception as e:
            print(f"Error in play command: {e}")
            await ctx.followup.send("An error occurred while trying to play the song.")


    @client.slash_command(name="clear_queue", description="Clear the current song queue")
    async def clear_queue(interaction: Interaction):
        ctx = interaction
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.response.send_message("Queue cleared!")
        else:
            await ctx.response.send_message("There is no queue to clear.")

    @client.slash_command(name="pause", description="Pause the current song")
    async def pause(interaction: Interaction):
        ctx = interaction
        try:
            voice_clients[ctx.guild.id].pause()
            await ctx.response.send_message("Paused playback.")
        except Exception as e:
            print(f"Error in pause: {e}")
            await ctx.response.send_message("Couldn't pause playback.")

    @client.slash_command(name="resume", description="Resume playback")
    async def resume(interaction: Interaction):
        ctx = interaction
        try:
            voice_clients[ctx.guild.id].resume()
            await ctx.response.send_message("Resumed playback.")
        except Exception as e:
            print(f"Error in resume: {e}")
            await ctx.response.send_message("Couldn't resume playback.")

    @client.slash_command(name="stop", description="Stop playback and disconnect the bot")
    async def stop(interaction: Interaction):
        ctx = interaction
        try:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
            await ctx.response.send_message("Stopped and disconnected.")
        except Exception as e:
            print(f"Error in stop: {e}")
            await ctx.response.send_message("Couldn't stop the music.")

    @client.slash_command(name="queue", description="Add a song to the queue")
    async def queue(interaction: Interaction, url: str = SlashOption(description="YouTube URL or search term")):
        ctx = interaction
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []
        queues[ctx.guild.id].append(url)
        await ctx.response.send_message("Added to queue!")

    client.run(TOKEN)

if __name__ == "__main__":
    run_bot()
