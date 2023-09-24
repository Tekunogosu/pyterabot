#!/usr/bin/env python3
import datetime
import json
import os
import re
from typing import List, Callable, Tuple, Optional
from queue import Queue
import threading
import time
import logging

from twitchio import Channel, User, Message, Client
from twitchio.ext import commands, routines, eventsub
from twitchio.ext.commands import Command, Context

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from dotenv import load_dotenv

from utils import now, getenv

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
# logging.basicConfig(level=logging.DEBUG)


if os.getenv('USE_PYCHARM'):
    """ 
        Load the .env file so our environment variables are set, but only when using pycharm since it doesn't know how
        Set USE_PYCHARM in the environment variables within pycharm
        Set your variables in .env-template and rename it to .env
        
    """
    load_dotenv(f'{os.getcwd()}/.env')


class Spotify(spotipy.Spotify):
    next_song_info_time: float
    current_song_info: str
    def __init__(self):
        super().__init__(oauth_manager=SpotifyOAuth(
            redirect_uri='http://localhost:9180',
            scope=[
                'user-read-currently-playing',
                'user-read-playback-state',
            ],
        ))
        self.next_song_info_time = 0.0
        self.current_song_info = ''

    def get_current_song_str(self, force_response:bool=False) -> str:
        remaining = self.next_song_info_time - time.time()
        if self.next_song_info_time > 0 and time.time() < self.next_song_info_time:
            return f"{self.current_song_info} - Current song ends in {remaining:.0f} seconds"
            # logger.warning(f"called too soon; wait until current song ends in {remaining:.1f} seconds")
            # return self.current_song_info if force_response else ''

        pb = self.current_playback()
        if not pb:
            logger.error("failed to get current playback info from spotify API")
            return ''

        duration_ms = pb['item']['duration_ms']
        progress_ms = pb['progress_ms']
        remaining_ms = duration_ms - progress_ms
        remaining_seconds = remaining_ms / 60
        self.next_song_info_time = time.time() + remaining_seconds

        song_name = pb['item']['name']
        artists_str = ', '.join(a['name'] for a in pb['item']['artists'])
        full_str = f'{song_name} - {artists_str}'
        self.current_song_info = full_str
        return f"{self.current_song_info} - Ends in {remaining:.0f} seconds"



class TeraBot(commands.Bot):

    loaded_commands: dict = {}
    inbox: Queue
    outbox: Queue

    def __init__(self, inbox:Queue, outbox:Queue, spotify: Spotify, commands_file: Optional[str] = None):
        super().__init__(
            token=getenv('TWITCH_TOKEN'),
            prefix='!',
            initial_channels=[getenv('TWITCH_CHANNEL')],
        )
        self.spotify = spotify
        self.inbox = inbox
        self.outbox = outbox
        print("loading commands :D")
        self.load_commands(commands_file)


    def load_commands(self, file: Optional[str] = None):
        if file is None:
            return
        with open(file) as f:
            try:
                self.loaded_commands = json.load(f)
            except FileNotFoundError as fe:
                print(f"Unable to load commands {fe}")

        for k, v in self.loaded_commands.items():
            # TODO: Validation checking
            _cname = k
            _alias = v["alias"]
            _text = v["text"]

            print(f"Loading command: {_cname}")

            def _make_function(name, _txt):
                async def _command(ctx: Context):

                    txt = _txt.format(
                        commands=", ".join(self.commands.keys()),
                        **ctx.__dict__
                    )

                    await ctx.send(txt)

                this_new_cmd = self.command(name=name, aliases=_alias)(_command)
                return this_new_cmd

            new_cmd = _make_function(_cname, _text)
            setattr(self, _cname, new_cmd)
            print(f"command {_cname} Loaded...")

    # Called once the bot is ready, seems to be executed after event_join
    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'user id is | {self.user_id}')

    # Called whenever someone joins the channel
    async def event_join(self, channel: Channel, user: User):
        print(f'{datetime.datetime.now()} {self.nick} joined {channel.name}')

    async def event_message(self, message: Message) -> None:
        """runs every time a message is sent"""

        # we're seeing a message that we sent, so don't process out own output.
        if message.echo:
            return

        print(f'{now()}:{message.author.name}: "{message.content}"')

        # first check if the message contains a command meant for the bot.
        # we have to call this explicitly since we're overwriting event_message.
        await self.handle_commands(message)

        # Get the context directly from the bot
        ctx = await self.get_context(message)
        # print(f'{message.tags}')

        if message.tags['user-type'] == 'mod':
            # await ctx.send(f'Oh look its another mod.. how original : {message.author.name}')
            print(f'Oh look its another mod.. how original : {message.author.name}')
        else:
            if 'broadcaster' not in message.tags['badges']:
                # await ctx.send('regular user, how .. regular?')
                print('regular user, how .. regular?')

        # if 'tera' in message.content.lower():
        #     await ctx.send("tera blah blah blah")

    async def event_command_error(self, context: Context, error: Exception) -> None:
        # TODO: punish spammers of invalid commands. Maybe more than 5 within X seconds
        # TODO: Log to log file for bot
        print(f'{now()} ({error.args[0]}) sent by {context.author.name}')

        # await context.send(f"Invalid command {context.message.content}")
        print(f"Invalid command {context.message.content}")

    # @routines.routine(seconds=30, iterations=2)
    # async def dosomething(self, arg: str):
    #     print(f'Something happening here every 30s {arg}')
    #
    # @dosomething.after_routine
    # async def afterstuff(self):
    #     print(f'This happened after the routine')
    #
    # @dosomething.before_routine
    # async def beforestuff(self):
    #     print(f'this is doing some stuff before the routine')

    # @commands.command()
    # async def hello(self, ctx: Context):
    #     await ctx.send(f'Hello {ctx.author.name}!')
    #
    #     users = await self.get_webhook_subscriptions()
    #     print(f'{users}')

    @commands.command(name="register", aliases=['reg', 'signup', 'create'])
    async def register(self, ctx: Context):
        print(f'Registering a new user.... {ctx.author.name}')
        await ctx.send(f'Registered user {ctx.author.name}')

    @commands.command(name="reminder", aliases=['rem'])
    async def reminder(self, ctx: Context):
        # time based reminders
        print(ctx.message.content)

    @commands.command(name="song")
    async def reminder(self, ctx: Context):
        song_str = self.spotify.get_current_song_str()
        print("SONG STRING", song_str)
        if not song_str:
            return
        await ctx.send(song_str)

    # setup !pat in commands.json
    @commands.command(name="t")
    async def reminders(self, ctx: Context):

        reg = re.compile(r"@\w+")
        m = reg.search(ctx.message.content or '')

        print(f"looking in {ctx.message.content}")
        print("matched: ", m[0] if m else m)
        if m:
            await ctx.send(f"/me gently pats {m[0]}")


def main():
    commands_json_filepath = os.path.abspath(os.path.join(os.curdir, 'commands.json'))
    # https://developer.spotify.com/documentation/web-api/concepts/scopes
    spotify = Spotify()

    # print(f"{commands_json_filepath}")
    to_bot = Queue()
    from_bot = Queue()
    bot = TeraBot(to_bot, from_bot, spotify, commands_json_filepath)

    bot_thread = threading.Thread(target=bot.run, daemon=True)
    bot_thread.start()

    while True:
        time.sleep(1)
        while from_bot:
            msg = from_bot.get()
            print(f'bot sent a message to the main thread: {msg}')


if __name__ == '__main__':
    main()
