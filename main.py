#!/usr/bin/env python3
import datetime
import json
import os
import re
from typing import List, Callable, Tuple, Optional

from twitchio import Channel, User, Message, Client
from twitchio.ext import commands, routines, eventsub
from twitchio.ext.commands import Command, Context

import inspect

from dotenv import load_dotenv

from utils import now, vv


if os.getenv('USE_PYCHARM'):
    """ 
        Load the .env file so our environment variables are set, but only when using pycharm since it doesn't know how
        Set USE_PYCHARM in the environment variables within pycharm
        Set your variables in .env-template and rename it to .env
        
    """
    load_dotenv(f'{os.getcwd()}/.env')


class TeraBot(commands.Bot):

    loaded_commands: dict = {}

    def __init__(self, commands_file: Optional[str] = None):
        super().__init__(
            token=os.getenv('TWITCH_TOKEN'),
            prefix='!',
            initial_channels=[os.getenv('TWITCH_CHANNEL')],
        )
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

        if message.echo:
            return

        await self.handle_commands(message)

        print(f'{now()} "{message.content}" sent by {message.author.name}')

        # Get the context directly from the bot
        # ctx = await self.get_context(message)
        # print(f'{message.tags}')

        ctx = await self.get_context(message)

        if message.tags['user-type'] == 'mod':
            await ctx.send(f'Oh look its another mod.. how original : {message.author.name}')
        else:
            if 'broadcaster' not in message.tags['badges']:
                await ctx.send('regular user, how .. regular?')

        if 'tera' in message.content.lower():
            await ctx.send("tera blah blah blah")

    async def event_command_error(self, context: Context, error: Exception) -> None:
        # TODO: punish spammers of invalid commands. Maybe more than 5 within X seconds
        # TODO: Log to log file for bot
        print(f'{now()} ({error.args[0]}) sent by {context.author.name}')

        await context.send(f"Invalid command {context.message.content}")

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
        pass


    # setup !pat in commands.json
    @commands.command(name="t")
    async def reminders(self, ctx: Context):

        reg = re.compile(r"@\w+")
        m = reg.search(ctx.message.content)

        print(f"looking in {ctx.message.content}")
        print("matched: ", m[0])

        await ctx.send(f"/me gently pats {m[0]}")


if __name__ == '__main__':
    cmdjson = os.path.abspath(os.curdir + "/commands.json")
    print(f"{cmdjson}")
    bot = TeraBot(cmdjson)

    # this is a blocking call which starts your bot
    bot.run()
