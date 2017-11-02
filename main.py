import logging
import sqlite3
import os

from ruamel.yaml import YAML
import discord


LOGGING_FORMAT = '[%(levelname)s - %(name)s - %(asctime)s] %(message)s'

STAR_EMOJI_DEFAULT = ['\N{WHITE MEDIUM STAR}']
STARBOARD_THRESHOLD_DEFAULT = 3


class HTStars(discord.Client):
    def __init__(self):
        super().__init__()

        self.log = logging.getLogger('Bot')
        logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)

        self.yaml = YAML(typ='safe')
        try:
            with open('config.yml') as conf_file:
                self.config = self.yaml.load(conf_file)
        except FileNotFoundError:
            config = {}
            print('Config file generator:')
            print('Please enter the emoji you want as the stars (comma seperated):')
            e = input('> ')
            e = [i.strip() for i in e.split(' ')]
            config['emojis'] = e
            print('Please enter the threshold for staring a message:')
            n = ''
            while not n or not n.isdigit():
                n = input('> ')
            config['threshold'] = int(n)
            print('Please enter the guild id:')
            n = ''
            while not n or not n.isdigit():
                n = input('> ')
            config['guild'] = int(n)
            print('Please enter the starboard channel id:')
            n = ''
            while not n or not n.isdigit():
                n = input('> ')
            config['starboard'] = int(n)
            print('Please enter the starboard channel id:')
            t = ''
            while not t or not os.path.exists(t):
                t = input('> ')
            config['token_file'] = t

            with open('config.yml', 'w') as conf_file:
                self.yaml.dump(config, conf_file)
                self.config = config

        self.database = sqlite3.connect("htstars.sqlite")
        cursor = self.database.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS stars
                          (original_id INTEGER,
                           starboard_id INTEGER,
                           guild_id INTEGER,
                           author INTEGER,
                           message_content TEXT)""")
        self.database.commit()
        cursor.close()

        if self.config.get('guild') is None:
            raise Exception('Guild id not set in config')

        if self.config.get('starboard') is None:
            raise Exception('Starboard channel id not set in config')

        if self.config.get('token_file') is None:
            raise ValueError('No token file set')

    @staticmethod
    def star_emoji(stars):
        if 5 > stars >= 0:
            return '\N{WHITE MEDIUM STAR}'
        elif 10 > stars >= 5:
            return '\N{GLOWING STAR}'
        elif 25 > stars >= 10:
            return '\N{DIZZY SYMBOL}'
        else:
            return '\N{SPARKLES}'

    @staticmethod
    def star_gradient_colour(stars):
        p = stars / 13
        if p > 1.0:
            p = 1.0

        red = 255
        green = int((194 * p) + (253 * (1 - p)))
        blue = int((12 * p) + (247 * (1 - p)))
        return (red << 16) + (green << 8) + blue

    def get_emoji_message(self, message, stars):
        emoji = self.star_emoji(stars)

        if stars > 1:
            content = '{0} **{2}** {1.channel.mention} ID: {1.id}'.format(emoji, message, stars)
        else:
            content = '{0} {1.channel.mention} ID: {1.id}'.format(emoji, message)

        embed = discord.Embed(description=message.content)
        if message.embeds:
            data = message.embeds[0]
            if data.type == 'image':
                embed.set_image(url=data.url)

        if message.attachments:
            file = message.attachments[0]
            if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif')):
                embed.set_image(url=file.url)
            else:
                embed.add_field(
                    name='Attachment',
                    value='[{0.filename}]({0.url})'.format(file), inline=False)

        embed.set_author(name=message.author.display_name,
                         icon_url=message.author.avatar_url_as(format='png'))
        embed.timestamp = message.created_at
        embed.colour = self.star_gradient_colour(stars)
        return content, embed

    def start_bot(self):
        with open(self.config.get('token_file')) as f:
            token = f.read().split('\n')[0].strip()
        self.run(token, bot=self.config.get('is_bot', True))

    async def on_ready(self):
        cursor = self.database.cursor()
        cursor.execute("""SELECT * FROM stars""")
        res = cursor.fetchall()
        cursor.close()

        self.log.info('-----------------------')
        self.log.info('Connected to Discord as')
        self.log.info(self.user.name)
        self.log.info(self.user.id)
        self.log.info('Guild: {0} / {0.id}'.format(
            self.get_guild(self.config.get('guild'))))
        self.log.info('Starboard: {0} / {0.id}'.format(
            self.get_channel(self.config.get('starboard'))))
        self.log.info('Messages stared: {}'.format(len(res)))
        self.log.info('-----------------------')
        self.log.info('')

    async def on_message(self, message):
        if message.content == 'star.die' and message.author.id == 161508165672763392:
            self.database.close()
            await self.logout()

    async def on_message_delete(self, message):
        if message.guild is not None and message.guild.id == self.config.get('guild'):
            cursor = self.database.cursor()
            cursor.execute("""SELECT * FROM stars
                              WHERE original_id=?""", (message.id,))
            res = cursor.fetchall()

            for i in res:
                try:
                    message = await message.guild.get_channel(
                        self.config.get('starboard')).get_message(i[1])

                    await message.delete()
                except discord.errors.NotFound:
                    pass

                cursor.execute("""DELETE FROM stars
                                  WHERE original_id=?""", (message.id,))
                self.database.commit()

    async def on_raw_reaction_add(self, emoji, message_id, channel_id, user_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == self.config.get('guild'):
            if emoji.name in self.config.get('stars', STAR_EMOJI_DEFAULT):
                message = await chan.get_message(message_id)
                if user_id == message.author.id:
                    await message.remove_reaction(emoji, message.author)
                    return

                await self.action(message_id, channel_id, user_id)

    async def on_raw_reaction_clear(self, message_id, channel_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == self.config.get('guild'):
            cursor = self.database.cursor()
            cursor.execute("""SELECT * FROM stars
                              WHERE original_id=?""", (message_id,))
            res = cursor.fetchall()

            for i in res:
                try:
                    message = await chan.guild.get_channel(
                        self.config.get('starboard')).get_message(i[1])

                    await message.delete()
                except discord.errors.NotFound:
                    pass

                cursor.execute("""DELETE FROM stars
                                  WHERE original_id=?""", (message_id,))
                self.database.commit()

    async def on_raw_reaction_remove(self, emoji, message_id, channel_id, user_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == self.config.get('guild'):
            if emoji.name in self.config.get('stars', STAR_EMOJI_DEFAULT):
                await self.action(message_id, channel_id, user_id)

    async def action(self, message_id, channel_id, user_id):
        target_message = await self.get_channel(channel_id).get_message(message_id)

        count = 0
        for i in target_message.reactions:
            if i.emoji in self.config.get('stars', STAR_EMOJI_DEFAULT):
                count = i.count
                break

        channel = self.get_channel(self.config.get('starboard'))

        cursor = self.database.cursor()
        cursor.execute("""SELECT * FROM stars
                          WHERE original_id=?""", (message_id,))
        res = cursor.fetchall()

        if res:
            try:
                message = await channel.get_message(res[0][1])

                if count >= self.config.get('threshold', STARBOARD_THRESHOLD_DEFAULT):
                    content, embed = self.get_emoji_message(target_message, count)

                    await message.edit(content=content, embed=embed)
                else:
                    await message.delete()
            except discord.errors.NotFound:
                cursor.execute("""DELETE FROM stars
                                  WHERE original_id=?""", (message_id,))
                self.database.commit()
                res = []

        if not res:
            if channel_id != self.config.get('starboard'):
                if count >= self.config.get('threshold', STARBOARD_THRESHOLD_DEFAULT):
                    content, embed = self.get_emoji_message(target_message, count)
                    message = await channel.send(content, embed=embed)

                    cursor.execute("""INSERT INTO stars (original_id,
                                                         starboard_id,
                                                         guild_id,
                                                         author,
                                                         message_content)
                                      VALUES (?, ?, ?, ?, ?)""",
                                      (message_id,
                                       message.id,
                                       channel.guild.id,
                                       target_message.author.id,
                                       target_message.content))
                    self.database.commit()
                    cursor.close()


if __name__ == '__main__':
    HTStars().start_bot()
