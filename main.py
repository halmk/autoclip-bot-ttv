import os
from os.path import expanduser
import click
from gensim.models import word2vec
import logging
import autoclip


@click.group()
def cli():
    pass


@click.command()
def configure():
    user = input("Username: ")
    client_id = input("Twitch Client ID: ")
    client_secret = input("Twitch Client Secret: ")
    user_token = input("User Token: ")
    home = expanduser('~')
    autoclip_dir = os.path.join(home, '.autoclip-ttv')
    os.makedirs(autoclip_dir, exist_ok=True)
    autoclip_config = os.path.join(autoclip_dir, 'config')
    with open(autoclip_config, 'w') as f:
        f.write(f"{user},{client_id},{client_secret},{user_token}")


@click.command()
@click.option('--streamer', '-s')
def train(streamer):
    click.echo("train")

    chatdir = os.path.join(os.getcwd(), 'chat')
    textlist = []
    texts = os.listdir(os.path.join(chatdir, streamer))
    for text in texts:
        textlist.append(os.path.join(chatdir, os.path.join(streamer, text)))

    chat_list = []
    for textpath in textlist:
        with open(textpath, 'r') as f:
            chat = []
            for s in f:
                comments = s.split()[2:]
                for comment in comments:
                    chat.append(comment)
            chat_list.append(chat)

    print(len(chat_list), sum([len(chat) for chat in chat_list]))

    handler = logging.StreamHandler()
    handler.terminator = ""
    #logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s\r', level=logging.INFO, handlers=[handler])
    logging.basicConfig(format='%(asctime)s: %(message)s\r', level=logging.INFO, handlers=[handler])
    model = word2vec.Word2Vec(chat_list, vector_size=100, min_count=5, window=5, epochs=1000)
    model.save("./model/{streamer}_chat.model".format(streamer=streamer))


@click.command()
@click.option('--streamer', '-s')
@click.option('--output', '-o', required=True)
@click.option('--category', '-c')
@click.option('--message-length', '-m', default=20)
@click.option('--recent-chat', '-l', default=10)
@click.option('--diff-clip', '-d', default=30.0)
def run(streamer, output, category, message_length, recent_chat, diff_clip):
    click.echo("run")
    print("Streamer : " + streamer)
    print("Output(json or mysql) : " + output)
    print("Message Length Limit(words) : " + str(message_length))
    print("Recent Chat Limit(seconds) : " + str(recent_chat))
    print("Diff Clip(seconds) : " + str(diff_clip))

    home = expanduser('~')
    autoclip_dir = os.path.join(home, '.autoclip-ttv')
    os.makedirs(autoclip_dir, exist_ok=True)
    autoclip_config = os.path.join(autoclip_dir, 'config')
    with open(autoclip_config, 'r') as f:
        s = f.readline()
    user = s.split(',')[0]
    client_id = s.split(',')[1]
    client_secret = s.split(',')[2]
    user_token = s.split(',')[3]
    print(f'User: {user}, Output: {output}, Category: {category}')

    ## 既存のモデルをロードする
    model = word2vec.Word2Vec.load(f'./model/{streamer}_chat.model')

    bot = autoclip.Bot(
        user=user,
        client_id=client_id,
        client_secret=client_secret,
        user_token=user_token,
        streamer=streamer,
        category=category,
        model=model,
        output=output,
        message_length=message_length,
        recent_chat=recent_chat,
        diff_clip=diff_clip
    )
    bot.start()


def main():
    cli()

if __name__ == '__main__':
    cli.add_command(configure)
    cli.add_command(train)
    cli.add_command(run)
    main()
