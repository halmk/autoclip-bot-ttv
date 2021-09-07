import os
from os.path import expanduser
import click
from gensim.models import word2vec
import logging
import autoclip


@click.command()
@click.argument('mode')
@click.option('--streamer', '-s')
def cmd(mode, streamer):
    msg = "Mode: {mode}, Streamer: {streamer}".format(mode=mode, streamer=streamer)
    click.echo(msg)

    if mode == 'configure':
        configure()
    elif mode == 'train':
        train(streamer)
    elif mode == 'run':
        run(streamer)
    else:
        pass


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


def run(streamer):
    click.echo("run")

    home = expanduser('~')
    autoclip_dir = os.path.join(home, '.autoclip-ttv')
    os.makedirs(autoclip_dir, exist_ok=True)
    autoclip_config = os.path.join(autoclip_dir, 'config')
    with open(autoclip_config, 'r') as f:
        s = f.readline()
    print(s)
    user = s.split(',')[0]
    client_id = s.split(',')[1]
    client_secret = s.split(',')[2]
    user_token = s.split(',')[3]
    print(user, client_id, client_secret, user_token)

    ## 既存のモデルをロードする
    model = word2vec.Word2Vec.load(f'./model/{streamer}_chat.model')

    bot = autoclip.Bot(
        user=user,
        client_id=client_id,
        client_secret=client_secret,
        user_token=user_token,
        streamer=streamer,
        model=model
    )
    bot.start()


def main():
    cmd()

if __name__ == '__main__':
    main()
