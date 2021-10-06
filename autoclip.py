from irc.bot import SingleServerIRCBot
import logging
import time
import threading
from datetime import datetime
import requests
import json
import os
import numpy as np
import csv
import pandas as pd
import pymysql.cursors
import dj_database_url


SERVER = 'irc.chat.twitch.tv'
PORT = 6667


class Bot(SingleServerIRCBot):
    # 初期化
    def __init__(self, user, client_id, client_secret, user_token, streamer, category, model, output, hypewords=['KEKW', 'LUL', 'PogU', 'Pog', 'ｗｗｗ', 'おおお']):
        self.user = user
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_token = user_token
        self.irc_token = f'oauth:{self.user_token}'
        self.app_token = self.get_token()
        self.streamer = streamer
        self.channel = '#' + streamer
        self.category = category
        self.model = model
        self.output = output
        self.set_user_id(user)
        self.set_streamer_id(streamer)
        self.set_logfile(streamer)
        self.hype = 0
        self.hypewords = hypewords
        self.que = []
        self.df = pd.DataFrame()
        self.start_time = time.time()
        self.last_clipped = time.time()
        self.clip_rate_remain = 600
        print(SERVER, PORT, self.irc_token, self.user)
        SingleServerIRCBot.__init__(self, [(SERVER, PORT, self.irc_token)], self.user, self.user)

        os.makedirs('./hype', exist_ok=True)
        csv_file = f'./hype/{self.streamer}.csv'
        with open(csv_file, 'a') as f:
            writer = csv.writer(f)
            header = ['datetime', 'hype', 'outlier']
            writer.writerow(header)


    def on_welcome(self, c, e):
        print('Joining ' + self.channel)

        # You must request specific capabilities before you can use them
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join(self.channel)
        print('Joined ' + self.channel)


    def on_pubmsg(self, c, e):
        # チャットユーザとチャットメッセージを取得
        user = e.source.split('!')[0]
        chat = e.arguments[0]
        if len(chat) >= 20 or chat[0]=='!' or chat[0]=='@' or user=='nightbot' or user=='streamelements':
            return
        sim = self.eval_chat(chat=chat, metric='avg')

        # queを更新
        self.que.append({'sim': sim, 'time': time.time()})
        while len(self.que) != 0:
            d_t = time.time() - self.que[0]['time']
            if d_t >= 10:
                #print(f"deleted: {self.que[0]['sim']:.2f}")
                self.que = self.que[1:]
            else:
                break

        hype_sum = sum([el['sim'] for el in self.que])
        df_tmp = pd.Series([hype_sum])
        self.df = self.df.append(df_tmp, ignore_index=True)
        lim = (self.df.quantile(0.75)[0] - self.df.quantile(0.25)[0])*1.5
        outlier = self.df.quantile(0.75)[0] + lim
        crt_secs = time.time() - self.start_time

        # csvファイルに書き込む
        csv_file = f'./hype/{self.streamer}.csv'
        with open(csv_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([f'{crt_secs:.2f}', f'{hype_sum:.2f}', f'{outlier:.2f}'])

        diff_clipped = time.time() - self.last_clipped
        crt = datetime.fromtimestamp(time.time())
        crt_date = f'{crt.hour:02}:{crt.minute:02}:{crt.second:02}'
        if hype_sum >= outlier and diff_clipped > 30.0:
            thread = threading.Thread(target=self.create_clip)
            thread.start()
            self.que = []
            self.last_clipped = time.time()

        # コメント情報を標準出力
        last_clipped_secs = self.last_clipped - self.start_time
        print(f"Channel : {self.channel} , Date : [{crt_date}]\nUser : {user}\nChat({len(chat)}) : {chat}\nHype : {sim:.2f}, Hype_sum : {hype_sum:.2f}, Outlier : {outlier:.2f}\nCurrent : {crt_secs:.2f}, Last clipped : {last_clipped_secs:.2f}, Rate remain : {self.clip_rate_remain}\n")
        #print(f"Channel : {self.channel} , Date : [{crt.hour:02}:{crt.minute:02}:{crt.second:02}] , User : {user} , Chat : {chat} , Hype : {sim:.2f}, Hype_sum : {hype_sum:.2f}", end='\r')

        return


    def connect_to_database(self):
        database = dj_database_url.parse(self.output)
        print(database)
        # Connect to the database
        connection = pymysql.connect(
            host=database['HOST'],
            user=database['USER'],
            password=database['PASSWORD'],
            database=database['NAME'],
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection


    def write_clipinfo(self, clip_id):
        data = {}
        data["clip_id"] = clip_id
        data["url"] = f'https://clips.twitch.tv/{clip_id}'
        data["embed_url"] = f'https://clips.twitch.tv/embed?clip={clip_id}'
        data["broadcaster_id"] = self.streamer_id
        data["broadcaster_name"] = self.streamer
        data["creator_id"] = self.user_id
        data["creator_name"] = self.user
        data["created_at"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        if self.output.split('.')[-1] == 'json':
            with open(self.output, 'r') as f:
                json_dict = json.load(f)
            with open(self.output, 'w') as f:
                json_dict["clips"].append(data)
                json.dump(json_dict,f,indent=4)
        else:
            connection = self.connect_to_database()
            with connection:
                with connection.cursor() as cursor:
                    # Create a new record
                    sql = "INSERT INTO `app_autoclip` (`clip_id`, `url`, `embed_url`, `broadcaster_id`, `broadcaster_name`, `creator_id`, `creator_name`, `created_at`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                    cursor.execute(sql, (data['clip_id'], data['url'], data['embed_url'], data['broadcaster_id'], data['broadcaster_name'], data['creator_id'], data['creator_name'], data['created_at']))

                connection.commit()


    def get_token(self):
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        res = requests.post('https://id.twitch.tv/oauth2/token', params=params)
        token = json.loads(res.text)['access_token']
        return token


    def get_request(self, url, params, count=0):
        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self.app_token}'
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 401:
            if count > 0:
                time.sleep(3)
            if count > 1:
                raise Exception
            self.app_token = self.get_token()
            return self.get_request(url, params, count+1)
        else:
            print(f"Rate-limit: Remaining:{response.headers.get('Ratelimit-Remaining')}, Reset:{response.headers.get('Ratelimit-Reset')}")
            response_json = response.json()
            return response_json


    def create_clip_request(self):
        headers = {
            'Client-ID': "gp762nuuoqcoxypju8c569th9wz7q5",
            'Authorization': f'Bearer {self.user_token}'
        }
        params = {
            'broadcaster_id': self.streamer_id
        }

        response = requests.post('https://api.twitch.tv/helix/clips', headers=headers, params=params)
        self.clip_rate_remain = response.headers["Ratelimit-Remaining"]
        status = response.status_code
        if status == 404:
            print(response)
            return None
        #print(response.headers)
        content = response.json()
        print(content)
        return content["data"][0]["id"]


    def create_clip(self):
        current_category = self.get_stream_category()
        if self.category != current_category:
            print("Target category is " + self.category + ", but current stream category is " + current_category + ".")
            return

        time.sleep(15)
        crt = datetime.fromtimestamp(time.time())
        crt_date = f'{crt.hour:02}:{crt.minute:02}:{crt.second:02}'
        clip_id = self.create_clip_request()
        if clip_id is not None:
            self.write_clipinfo(clip_id)
            clip_file = f'./hype/{self.streamer}_clips.txt'
            with open(clip_file, 'a') as f:
                f.write(f'{crt_date},{clip_id}\n')


    # Get Users API を使用して配信者のIDを取得する
    def get_user_id(self, user):
        params = (
            ('login', user),
        )
        content = self.get_request('https://api.twitch.tv/helix/users', params=params)
        print(content)
        id = content["data"][0]["id"]
        return id


    # IDを取得して self.streamer_id にセットする
    def set_streamer_id(self, streamer):
        self.streamer_id = self.get_user_id(streamer)


    def set_user_id(self, user):
        self.user_id = self.get_user_id(user)


    # 配信中のカテゴリを取得する
    def get_stream_category(self):
        params = (
            ('user_id', self.streamer_id)
        )
        content = self.get_request('https://api.twitch.tv/helix/streams', params=params)
        print(content)
        category = content["data"][0]["game_name"]
        return category


    # ログファイルのファイルパスを指定する
    def set_logfile(self, channel):
        os.makedirs(f"./logs/{channel}", exist_ok=True)
        dt = datetime.fromtimestamp(time.time())
        self.LOGFILE = f'./logs/{channel}/{dt.month}-{dt.day}.log'


    # ロギング形式の指定
    def set_logging(self):
        logging.basicConfig(level=logging.DEBUG,
            format="%(asctime)s - %(message)s",
            datefmt="%Y-%m-%d_%H:%M:%S",
            handlers=[logging.FileHandler(self.LOGFILE, encoding='utf-8')])


    # cos類似度を計算
    def cos_sim(self, v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


    # 機械学習モデルでチャットメッセージを評価する
    def eval_chat(self, chat, metric='avg'):
        try:
            sim = 0
            # 比較元の単語のベクトルを取得する
            v_hypes = []
            for sent in self.hypewords:
                try:
                    v_hypes.append(self.model.wv[sent])
                except:
                    pass
            count = len(chat.split())
            comments = chat.split()
            for comment in comments:
                try:
                    # コメントの単語ベクトルを取得
                    v1 = self.model.wv[comment]
                    # コメントの単語ベクトルとHypewordsとのHype値の最大値を求める
                    mx_sim = max([self.cos_sim(v1,vs) for vs in v_hypes])
                    if metric == 'max':
                        sim = max(sim, mx_sim)
                    if metric == 'avg':
                        sim += mx_sim / count
                except KeyError:
                    pass
        except KeyError as e:
            print(e)
            return 0.05
        return max(sim, 0.05)
