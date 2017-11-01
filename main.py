import sqlite3

import discord


STAR_EMOJI = b'\xe2\xad\x90'.decode('utf-8')
STARBOARD_THRESHOLD = 3
GUILD_ID = 282219466589208576
STARBOARD_ID = 375361337464979467


class HTStars(discord.Client):
    def __init__(self):
        discord.Client.__init__(self)

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
            content = f'{emoji} **{stars}** {message.channel.mention} ID: {message.id}'
        else:
            content = f'{emoji} {message.channel.mention} ID: {message.id}'


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
                embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

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

        print('Starboard? More like.. Um.. Draobrats?')

    async def on_message(self, message):
        if message.content == 'star.die' and message.author.id == 161508165672763392:
            self.database.close()
            await self.logout()

    async def on_message_delete(self, message):
        if message.guild is not None and message.guild.id == GUILD_ID:
            cursor = self.database.cursor()
            cursor.execute("""SELECT * FROM stars WHERE original_id=?""", (message.id,))
            res = cursor.fetchall()

            for i in res:
                try:
                    message = await message.guild.get_channel(STARBOARD_ID).get_message(i[1])

                    await message.delete()
                except discord.errors.NotFound:
                    pass

                cursor.execute("""DELETE FROM stars WHERE original_id=?""", (message.id,))
                self.database.commit()

    async def on_raw_reaction_add(self, emoji, message_id, channel_id, user_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == GUILD_ID:
            if emoji.name == STAR_EMOJI:
                await self.action(message_id, channel_id, user_id)

    async def on_raw_reaction_clear(self, message_id, channel_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == GUILD_ID:
            cursor = self.database.cursor()
            cursor.execute("""SELECT * FROM stars WHERE original_id=?""", (message_id,))
            res = cursor.fetchall()

            for i in res:
                try:
                    message = await chan.guild.get_channel(STARBOARD_ID).get_message(i[1])

                    await message.delete()
                except discord.errors.NotFound:
                    pass

                cursor.execute("""DELETE FROM stars WHERE original_id=?""", (message_id,))
                self.database.commit()

    async def on_raw_reaction_remove(self, emoji, message_id, channel_id, user_id):
        chan = self.get_channel(channel_id)
        if chan.guild is not None and chan.guild.id == GUILD_ID:
            if emoji.name == STAR_EMOJI:
                await self.action(message_id, channel_id, user_id)

    async def action(self, message_id, channel_id, user_id):
        target_message = await self.get_channel(channel_id).get_message(message_id)

        count = 0
        for i in target_message.reactions:
            if i.emoji == STAR_EMOJI:
                count = i.count
                break

        channel = self.get_channel(STARBOARD_ID)

        cursor = self.database.cursor()
        cursor.execute("""SELECT * FROM stars WHERE original_id=?""", (message_id,))
        res = cursor.fetchall()

        if res:
            try:
                message = await channel.get_message(res[0][1])

                if count >= STARBOARD_THRESHOLD:
                    content, embed = self.get_emoji_message(target_message, count)

                    await message.edit(content=content, embed=embed)
                else:
                    await message.delete()
            except discord.errors.NotFound:
                cursor.execute("""DELETE FROM stars WHERE original_id=?""", (message_id,))
                self.database.commit()
                res = []

        if not res:
            if channel_id != STARBOARD_ID:
                if count >= STARBOARD_THRESHOLD:
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
    bot.run(open('token.txt').read().split('\n')[0])
