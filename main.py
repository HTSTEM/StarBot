import sqlite3
from ruamel.yaml import YAML

import discord


class HTStars(discord.Client):
    def __init__(self):
        super().__init__()
        self.yaml = YAML(typ='safe')
        with open('config.yml') as conf_file:
            self.config = self.yaml.load(conf_file)
        
        # get stars from config, defaults to 
        try:
            self.STAR_EMOJI = list(self.config['stars'])
        except KeyError:
            self.STAR_EMOJI = list(b'\xe2\xad\x90'.decode('utf-8'))

        try: 
            self.THRESH = int(self.config['threshold'])
        except KeyError:
            self.THRESH = 3
            
        try:
            self.GUILD_ID = int(self.config['guild'])
        except KeyError: raise Exception('`guild` is missing from config.yml')
            
        try:
            self.STARBOARD_ID = int(self.config['starboard'])
        except KeyError: raise Exception('`starboard` is missing from config.yml')
            
    def star_emoji(self, stars):
        if 5 > stars >= 0:
            return '\N{WHITE MEDIUM STAR}'
        elif 10 > stars >= 5:
            return '\N{GLOWING STAR}'
        elif 25 > stars >= 10:
            return '\N{DIZZY SYMBOL}'
        else:
            return '\N{SPARKLES}'

    def star_gradient_colour(self, stars):
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
                embed.add_field(name='Attachment', value='[{file.filename}]({file.url})'.format(), inline=False)

        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url_as(format='png'))
        embed.timestamp = message.created_at
        embed.colour = self.star_gradient_colour(stars)
        return content, embed


    async def on_ready(self):
        self.database = sqlite3.connect("htstars.sqlite")
        cursor = self.database.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS stars (original_id INTEGER, starboard_id INTEGER, guild_id INTEGER, author INTEGER, message_content TEXT)""")
        self.database.commit()
        cursor.close()

        print('-----------------------')
        print('Connected to Discord as')
        print(self.user.name)
        print(self.user.id)
        print('Guild: {0} / {0.id}\nStarboard: {1} / {1.id}'.format(self.get_guild(self.GUILD_ID), self.get_channel(self.STARBOARD_ID)))
        print('-----------------------\n')

    async def on_message(self, message):
        if message.content == 'star.die' and message.author.id == self.user.id:
            self.database.close()
            await self.logout()

    async def on_message_delete(self, message):
        if message.guild is not None and message.guild.id == self.GUILD_ID:
            cursor = self.database.cursor()
            cursor.execute("""SELECT * FROM stars WHERE original_id=?""", (message.id,))
            res = cursor.fetchall()

            for i in res:
                try:
                    message = await message.guild.get_channel(self.STARBOARD_ID).get_message(i[1])

                    await message.delete()
                except discord.errors.NotFound:
                    pass

                cursor.execute("""DELETE FROM stars WHERE original_id=?""", (message.id,))
                self.database.commit()

    async def on_raw_reaction_add(self, emoji, message_id, channel_id, user_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == self.GUILD_ID:
            if emoji.name in self.STAR_EMOJI:
                await self.action(message_id, channel_id, user_id)

    async def on_raw_reaction_clear(self, message_id, channel_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == self.GUILD_ID:
            cursor = self.database.cursor()
            cursor.execute("""SELECT * FROM stars WHERE original_id=?""", (message_id,))
            res = cursor.fetchall()

            for i in res:
                try:
                    message = await chan.guild.get_channel(self.STARBOARD_ID).get_message(i[1])

                    await message.delete()
                except discord.errors.NotFound:
                    pass

                cursor.execute("""DELETE FROM stars WHERE original_id=?""", (message_id,))
                self.database.commit()

    async def on_raw_reaction_remove(self, emoji, message_id, channel_id, user_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == self.GUILD_ID:
            if emoji.name in self.STAR_EMOJI:
                await self.action(message_id, channel_id, user_id)

    async def action(self, message_id, channel_id, user_id):
        target_message = await self.get_channel(channel_id).get_message(message_id)

        count = 0
        for i in target_message.reactions:
            if i.emoji in self.STAR_EMOJI:
                count = i.count
                break

        channel = self.get_channel(self.STARBOARD_ID)

        cursor = self.database.cursor()
        cursor.execute("""SELECT * FROM stars WHERE original_id=?""", (message_id,))
        res = cursor.fetchall()

        if res:
            try:
                message = await channel.get_message(res[0][1])

                if count >= self.THRESH:
                    content, embed = self.get_emoji_message(target_message, count)

                    await message.edit(content=content, embed=embed)
                else:
                    await message.delete()
            except discord.errors.NotFound:
                cursor.execute("""DELETE FROM stars WHERE original_id=?""", (message_id,))
                self.database.commit()
                res = []

        if not res:
            if channel_id != self.STARBOARD_ID:
                if count >= self.THRESH:
                    content, embed = self.get_emoji_message(target_message, count)

                    # embed = discord.Embed()
                    # embed.timestamp = target_message.created_at
                    # embed.description = target_message.content
                    # embed.set_author(name=target_message.author.name, icon_url=target_message.author.avatar_url_as(format='png'))
                    # message = await channel.send(':star: **{}** <#{}> ID: {}'.format(count, channel_id, message_id), embed=embed)
                    message = await channel.send(content, embed=embed)

                    cursor.execute("""INSERT INTO stars (original_id, starboard_id, guild_id, author, message_content)
                                      VALUES (?, ?, ?, ?, ?)""", (message_id, message.id, channel.guild.id, target_message.author.id, target_message.content))
                    self.database.commit()
                    cursor.close()

if __name__ == '__main__':
    bot = HTStars()
    bot.run(open(bot.config['token_file']).read().split('\n')[0])

