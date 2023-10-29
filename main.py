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

from spotipy.client import Spotify as Spotipy
from spotipy.oauth2 import SpotifyOAuth


from dotenv import load_dotenv

from utils import now, getenv

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)


#if os.getenv('USE_PYCHARM'):
#    """ 
#        Load the .env file so our environment variables are set, but only when using pycharm since it doesn't know how
#        Set USE_PYCHARM in the environment variables within pycharm
#        Set your variables in .env-template and rename it to .env
#        
#    """
load_dotenv(f'{os.getcwd()}/.env')


class Spotify(Spotipy):
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
        """
        implement force_response
        needed test cases:
        * no song playing (and hasn't in a while so the api call will not return a current song)
        """
        if self.next_song_info_time > 0 and time.time() < self.next_song_info_time:
            remaining = self.next_song_info_time - time.time()
            return f"{self.current_song_info} - Ends in {remaining//60:.0f}:{remaining%60//1:>02.0f} seconds"
            # logger.warning(f"called too soon; wait until current song ends in {remaining:.1f} seconds")
            # return self.current_song_info if force_response else ''

        #TODO:separate function
        pb = None
        try:
            pb = self.current_playback()
        except Exception as e1:
            time.sleep(1)
            try:
                pb = self.current_playback()
            except Exception as e2:
                logger.exception('Failed to get current playback information from spotify twice in a row; errors:\n%s\n%s', e1, e2)
        if not pb:
            logger.error("failed to get current playback info from spotify API")
            return ''

        duration_ms = pb['item']['duration_ms']
        progress_ms = pb['progress_ms']
        remaining_ms = duration_ms - progress_ms
        remaining_seconds = remaining_ms / 1000
        self.next_song_info_time = time.time() + remaining_seconds

        song_name = pb['item']['name']
        artists_str = ', '.join(a['name'] for a in pb['item']['artists'])
        full_str = f'{song_name} - {artists_str}'
        self.current_song_info = full_str
        remaining = remaining_seconds
        return f"{self.current_song_info} - Ends in {remaining//60:.0f}:{remaining%60//1:>02.0f}"


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
        logger.debug("loading commands :D")
        self.load_commands(commands_file)


    def load_commands(self, file: Optional[str] = None):
        if file is None:
            return
        with open(file) as f:
            try:
                self.loaded_commands = json.load(f)
            except FileNotFoundError as fe:
                logger.warning(f"Unable to load commands {fe}")

        for k, v in self.loaded_commands.items():
            # TODO: Validation checking
            _cname = k
            _alias = v["alias"]
            _text = v["text"]

            logger.debug(f"Loading command: {_cname}")

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
            logger.debug(f"command {_cname} Loaded...")

    # Called once the bot is ready, seems to be executed after event_join
    async def event_ready(self):
        logger.info(f'Logged in as | {self.nick}')
        logger.info(f'user id is | {self.user_id}')

    # Called whenever someone joins the channel
    async def event_join(self, channel: Channel, user: User):
        logger.info(f'{datetime.datetime.now()} {self.nick} joined {channel.name}')

    async def event_message(self, message: Message) -> None:
        """runs every time a message is sent"""

        # we're seeing a message that we sent, so don't process out own output.
        if message.echo:
            return

        logger.info(f'{now()}:{message.author.name}: "{message.content}"')

        ctx = await self.get_context(message)

        # first check if the message contains a command meant for the bot.
        # we have to call this explicitly since we're overwriting event_message.
        await self.do_handle_command(message, ctx)
        # logger.debug(f'{message.tags}')

        if self.is_moderator(message):
            pass
        elif self.is_streamer(message):
            pass
        elif self.is_viewer(message):
            pass

    async def do_handle_command(self, message:Message, ctx:Optional[Context]=None):
        if ctx is None:
            ctx = await self.get_context(message)

        """
        2023-10-01 10:41:01.617230:violet_revenant: "!song"
        ctx <twitchio.ext.commands.core.Context object at 0x7f6bad5bbe50>
        2023-10-01 10:41:01.647477 (('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))) sent by violet_revenant
        Invalid command !song

        2023-10-01 10:42:28.539541:violet_revenant: "!song"
        ctx <twitchio.ext.commands.core.Context object at 0x7f6bad5cd790>
        SONG STRING Two Dots - Lusine - Ends in 2:59
        """
        if not ctx.prefix:
            logger.debug(
                f"skipping command processing because `not ctx.prefix`: "
                f"`not {ctx.prefix}`"
            )
        elif not ctx.is_valid:
            logger.info(
                f"skipping command processing because `not ctx.is_valid`: "
                f"`not {ctx.is_valid}`"
            )
        elif ctx.command is None:
            logger.debug("skipping command processing because `ctx.command is None`")
        else:
            logger.info(f"command: {ctx.command}, {ctx.command.full_name}")
            self.run_event("command_invoke", ctx)
            await ctx.command(ctx)

    async def event_command_error(self, context: Context, error: Exception) -> None:
        # TODO: punish spammers of invalid commands. Maybe more than 5 within X seconds
        # TODO: Log to log file for bot
        logger.info(f'{now()}:{context.author.name}:Failed to run command: ({error.args[0]})')

        # await context.send(f"Invalid command {context.message.content}")
        # logger.info(f"Invalid command {context.message.content}")

    def is_moderator(self, message:Message) -> bool:
        return message.tags['user-type'] == 'mod'
    def is_streamer(self, message:Message) -> bool:
        return 'broadcaster' in message.tags['badges']
    def is_viewer(self, message:Message) -> bool:
        if self.is_moderator(message) or self.is_streamer(message):
            return False
        return 'broadcaster' not in message.tags['badges']

    # @routines.routine(seconds=30, iterations=2)
    # async def dosomething(self, arg: str):
    #     logger.info(f'Something happening here every 30s {arg}')
    #
    # @dosomething.after_routine
    # async def afterstuff(self):
    #     logger.info(f'This happened after the routine')
    #
    # @dosomething.before_routine
    # async def beforestuff(self):
    #     logger.info(f'this is doing some stuff before the routine')

    # @commands.command()
    # async def hello(self, ctx: Context):
    #     await ctx.send(f'Hello {ctx.author.name}!')
    #
    #     users = await self.get_webhook_subscriptions()
    #     logger.info(f'helo command, self.get_webhook_subscriptions ("users"): {users}')

    @commands.command(name="register", aliases=['reg', 'signup', 'create'])
    async def register(self, ctx: commands.Context):
        print(f'Registering a new user.... {ctx.author.name}')
        await ctx.send(f'Registered user {ctx.author.name}')

    @commands.command(name="reminder", aliases=['rem'])
    async def reminder(self, ctx: Context):
        # time based reminders
        print(ctx.message.content)

    @commands.command(name="song")
    async def song(self, ctx: Context):
        song_str = self.spotify.get_current_song_str()
        print("SONG STRING", song_str)
        if not song_str:
            await ctx.send("Failed to get info from Spotify API")
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
    twitch_bot = TeraBot(to_bot, from_bot, spotify, commands_json_filepath)

    bot_thread = threading.Thread(target=twitch_bot.run, daemon=True)
    bot_thread.start()

    while True:
        time.sleep(1)
        while from_bot:
            msg = from_bot.get()
            print(f'bot sent a message to the main thread: {msg}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # quiet down other loggers
    loggers = [
        'twitchio.websocket',
        'twitchio.client',
        'urllib3.connectionpool',
        #'spotipy.client',
    ]
    for log_name in loggers:
        logging.getLogger(log_name).setLevel(level=logging.INFO)
    logging.getLogger('spotipy.client').setLevel(level=logging.DEBUG)

    main()
