import json
import os
import requests
import datetime

tg_token_api = os.environ['TELEGERAM_TOKEN']
ya_token_api = os.environ['YANDEX_API']
geocoder_api = os.environ['GEOCODER_API_KEY']
weather_api = os.environ['WEATHER_API_KEY']


url = 'https://api.telegram.org/'
bot_api = f'bot{tg_token_api}/'

def weather(event, context):
    global geocoder_api, ya_token_api, weather_api, bot_api, url, tg_token_api

    update = json.loads(event['body'])

    if 'message' in update:
        message_id = update['message']['message_id']
        chat_id = update['message']['chat']['id']

        if not ('text' in update['message'] or 'location' in update['message'] or 'voice' in update['message']):
            text = 'Я не могу ответить на такой тип сообщения.\n' \
                   'Но могу ответить на:\n' \
                   '- Текстовое сообщение с названием населенного пункта.\n' \
                   '- Голосовое сообщение с названием населенного пункта.\n' \
                   '- Сообщение с точкой на карте.\n'
            return send_sorry_mess(text, chat_id, message_id)

        if 'text' in update['message'] and update['message']['text'] in ['/start', '/help']:
            text = 'Я сообщу вам о погоде в том месте, которое сообщите мне.\n' \
                   'Я могу ответить на:\n' \
                   '- Текстовое сообщение с названием населенного пункта.\n' \
                   '- Голосовое сообщение с названием населенного пункта.\n' \
                   '- Сообщение с точкой на карте.\n'

            return send_sorry_mess(text, chat_id, message_id)

        if 'voice' in update['message']:
            file_id = update['message']['voice']['file_id']
            if update['message']['voice']['duration'] > 30:
                text = 'Я не могу понять голосовое сообщение длительность более 30 секунд.'
                return send_sorry_mess(text, chat_id, message_id)

            file_obj = requests.post(url + bot_api + 'getFile', json={'file_id': file_id}).json()['result']

            file_resp = requests.get(url + 'file/' + bot_api + f'{file_obj["file_path"]}')
            yandex_resp = requests.post('https://stt.api.cloud.yandex.net/speech/v1/stt:recognize',
                                        headers={
                                            'Authorization': f'Api-Key {ya_token_api}'},
                                        data=file_resp.content)

            address = json.loads(yandex_resp.text)['result']

            try:
                lat, lon = get_coo(address)
                answer = requests.get(
                    f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api}&lang=ru&units=metric').json()
                send_mess('voice', chat_id, message_id, address, answer)
            except:
                text = f'Я не нашел населенный пункт {address}.'
                return send_sorry_mess(text, chat_id, message_id)

        if 'text' in update['message']:
            address = update['message']['text']

            try:
                lat, lon = get_coo(address)
                answer = requests.get(
                    f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api}&lang=ru&units=metric').json()
                send_mess('text', chat_id, message_id, address, answer)
            except:
                text = f'Я не нашел населенный пункт {address}.'
                return send_sorry_mess(text, chat_id, message_id)

        if 'location' in update['message']:
            lat, lon = float(update['message']['location']['latitude']), float(
                update['message']['location']['longitude'])

            try:
                answer = requests.get(
                    f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api}&lang=ru&units=metric').json()
                send_mess('location', chat_id, message_id, lat, answer)
            except:
                text = 'Я не знаю какая погода в этом месте.'
                return send_sorry_mess(text, chat_id, message_id)

    return {
        'statusCode': 200,
    }

def send_mess(type, chat_id, message_id, address, answer):
    global url, bot_api, ya_token_api, weather_api

    if type == 'voice':
        text = f'Населенный пункт {address}.' \
               f'{answer["weather"][0]["description"].title()}.' \
               f'Температура {round(answer["main"]["temp"])}.' \
               f'Ощущается как {round(answer["main"]["feels_like"])}.' \
               f'Давление {round(answer["main"]["pressure"])}.' \
               f'Влажность {round(answer["main"]["humidity"])}.'

        voice = requests.post('https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize',
                              headers={'Authorization': f'Api-Key {ya_token_api}'},
                              data={
                                    'text': text,
                                    'lang': 'ru-RU',
                                    'voice': 'filipp',
                                })

        voice_file = b""
        for chunk in voice.iter_content(chunk_size=None):
            voice_file += chunk
        file = {'voice': ('voice.ogg', voice_file)}

        r = requests.post(url + bot_api + 'sendVoice' + "?chat_id=" + str(chat_id) + "?reply_to_message_id=" + str(message_id) + "&voice=", files=file,)

    else:
        r = requests.post(url + bot_api + 'sendMessage', json={'chat_id': chat_id,
                                                               'reply_to_message_id': message_id,
                                                               'text': f'{answer["weather"][0]["description"].title()}.\n'
                                                                       f'Температура {answer["main"]["temp"]} ℃, ощущается как {answer["main"]["feels_like"]} ℃.\n'
                                                                       f'Атмосферное давление {answer["main"]["pressure"]} мм рт. ст.\n'
                                                                       f'Влажность {answer["main"]["humidity"]} %.\n'
                                                                       f'Видимость {answer["visibility"]} метров.\n'
                                                                       f'Ветер {answer["wind"]["speed"]} м/с {(answer["wind"]["deg"])}.\n'
                                                                       f'Восход солнца {datetime.datetime.fromtimestamp(answer["sys"]["sunrise"] + 10800).strftime("%I:%M")} МСК.\n'
                                                                       f'Закат {datetime.datetime.fromtimestamp(answer["sys"]["sunset"] + 10800).strftime("%I:%M")} МСК.'})


def get_coo(address):
    r = requests.get(
        f'https://geocode-maps.yandex.ru/1.x/?apikey={geocoder_api}&geocode={address}&format=json').json()

    lat, lon = r["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"].split(' ')

    return lat, lon

def send_sorry_mess(text, chat_id, message_id):
    r = requests.post(url + bot_api + 'sendMessage',
                      json={'chat_id': chat_id, 'reply_to_message_id': message_id, 'text': text})

    return {
        'statusCode': 200,
    }






