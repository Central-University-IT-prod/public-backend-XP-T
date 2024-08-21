import os
import logging
import asyncio
import aiohttp
import faker
from datefinder import find_dates
from datetime import timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from models import (
    init_models,
    TelegramUser,
    Trip,
    Location,
    UserTrip,
    Invite,
    Note,
)
from core.config import OSM_HEADERS, YANDEX_HEADERS, FSQ_HEADERS
from map.route import Route

# 1
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)
# 1
load_dotenv()

NAME, AGE, BIO, LOCATION = range(4)
TRIP_NAME, TRIP_BIO, TRIP_HM, TRIP_LOCATION = range(4)
TRIP_PATCH_NAME_COMPLETE = 0
TRIP_PATCH_BIO_COMPLETE = 0
TRIP_ADD_LOCATION_COMPLETE = 0
TRIP_ADD_NOTE_ASK, TRIP_ADD_NOTE_COMPLETE = range(2)

CHANGE_NAME_COMPLETE = 0
CHANGE_BIO_COMPLETE = 0
CHANGE_AGE_COMPLETE = 0
CHANGE_LOCATION_COMPLETE = 0

LOCATION_WRONG_FORMAT = 'Неправильный формат сообщения.'
LOCATION_WRONG_FIRST_DATE = 'Неправильный формат первой даты.'
LOCATION_WRONG_SECOND_DATE = 'Неправильный формат второй даты.'
LOCATION_WRONG_FIRST_TIME = 'Неправильный формат первого времени.'
LOCATION_WRONG_SECOND_TIME = 'Неправильный формат второго времени.'

markup = InlineKeyboardMarkup(
    [[InlineKeyboardButton('Да, приступаем', callback_data='LOCATION')]]
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_db = await TelegramUser.get_telegram_user(telegram_id=user.id)
    if user_db:
        if len(update.message.text.split(' ')) == 2:
            code = update.message.text.split(' ')
            token = code[1]
            trip_id = await Invite.get_invite(token)

            if trip_id:
                if not await UserTrip.get_user_trip(
                    user_id=user.id,
                    trip_id=trip_id
                ) and await Trip.get_trip(trip_id):
                    user_trips = await UserTrip.get_user_trips_by_trip(
                        trip_id=trip_id)
                    for user_trip in user_trips:
                        tg_user = await TelegramUser.get_telegram_user(
                            user_trip.user)
                        trip = await Trip.get_trip(trip_id=trip_id)
                        await context.bot.send_message(
                            tg_user.chat_id,
                            f'В путешествии "{trip.name}" '
                            f'теперь еще один участник - {user_db.name}')
                    await UserTrip.add_user_trip(
                        user_id=user.id, trip_id=trip_id)
                    await update.message.reply_text(
                        'Вы успешно добавлены в путешествие.')
        await update.message.reply_text('Выберите, куда вы хотите перейти:',
                                        reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    await update.message.reply_text(
        'Привет, я телеграм-бот TravelMate! Я был создан для того, '
        'чтобы сделать твое путешествие идеальным. Давай познакомимся - '
        'Как тебя зовут?'
    )
    return NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет имя и спрашивает возраст"""
    name = update.message.text
    context.user_data.clear()

    context.user_data['name'] = name

    await update.message.reply_text(
        f'{name.capitalize()}, рад знакомству! Напиши сколько тебе лет.',
    )
    return AGE


async def age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет возраст и спрашивает геолокацию"""
    age = update.message.text

    for number in age:
        if not number.isdigit():
            await update.message.reply_text(
                'Напиши свой настоящий возраст ^_^',
            )
            return AGE
    age = int(age)
    if age < 3 or age > 150:
        await update.message.reply_text(
            'Напиши свой настоящий возраст ^_^',
        )
        return AGE

    context.user_data['age'] = age

    await update.message.reply_text(
        'Теперь напиши немного о себе. '
    )
    return BIO


async def bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет информацию о пользователе"""
    user = update.effective_user
    context.user_data['bio'] = update.message.text
    context.user_data['telegram_id'] = int(user.id)
    context.user_data['chat_id'] = int(update.message.chat_id)

    logger.info("Bio of %s: %s", user.first_name, update.message.text)

    await update.message.reply_text(
        'Отправь мне свою геолокацию или напиши свой '
        'город в формате "Страна, Город, Область/штат(по желанию)".',
    )

    return LOCATION


async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет локацию и спрашивает био пользователя."""
    user = update.effective_user
    user_location = update.message.location
    params = [
        ('lat', user_location.latitude),
        ('lon', user_location.longitude),
        ('format', 'json')]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://nominatim.openstreetmap.org/reverse',
            params=params
        ) as resp:
            response = await resp.json()
            country = response['address']['country']
            city = response['address']['city']

            context.user_data['city'] = city
            context.user_data['country'] = country

    logger.info(
        "TG Location of %s: %s / %s", user.first_name, country, city
    )
    await TelegramUser.add_telegram_user(
        telegram_id=context.user_data['telegram_id'],
        chat_id=context.user_data['chat_id'],
        name=context.user_data['name'],
        age=context.user_data['age'],
        bio=context.user_data['bio'],
        city=context.user_data['city'],
        country=context.user_data['country'],
        city_lat=str(user_location.latitude),
        city_lon=str(user_location.longitude)
        )
    logger.info('check location')
    await update.message.reply_text(
        'Спасибо, теперь твой профиль заполнен. '
        'Для добавления путешествий перейди в /menu')

    return ConversationHandler.END


def cities_keyboard(cities, func):
    keyboard = []
    choice_id = 1
    for city in cities:
        lat = city['lat']
        if len(lat) > 12:
            lat = lat[:12]
        lon = city['lon']
        if len(lon) > 12:
            lon = lon[:12]
        place_type = city['type']
        callback = func + str(lat) + '$' + str(lon) + '$'
        callback += place_type
        logger.info(callback)
        keyboard.append([
            InlineKeyboardButton(
                str(choice_id),
                callback_data=callback)
        ])
        choice_id += 1
    keyboard.append([InlineKeyboardButton(
        'Назад', callback_data='another_location')])

    return InlineKeyboardMarkup(keyboard)


def cities_template(cities):
    template = '<b>Выбери место:</b>\n'
    choice_id = 1
    for city in cities:
        address = city['type'] + ' ' + city['display_name']
        template += f'<i>№{choice_id}. {address}.</i>\n'
        choice_id += 1
    return template


async def location_hand(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Skips the location and asks for info about the user."""
    msg = update.message.text.split(', ')
    if len(msg) not in [2, 3]:
        await update.message.reply_text('Неверный формат, попробуйте снова.')
        return LOCATION
    params = [
        ('country', msg[0]),
        ('city', msg[1]),
        ('format', 'json'),
        ('addressdetails', 1),
        ('limit', 10)
    ]
    if len(msg) == 3:
        params += [('state', msg[2])]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://nominatim.openstreetmap.org/search',
            params=params,
            headers=OSM_HEADERS
        ) as resp:
            cities = await resp.json()
            logger.info(cities)

            if len(cities) == 0:
                await update.message.reply_text(
                    'Город не найден, попробуем найти его снова. '
                    'Отправь мне свою геолокацию или напиши свой '
                    'город в формате "Страна, Город, '
                    'Область/штат(по желанию)".',
                )

                return LOCATION

            await update.message.reply_text(
                cities_template(cities=cities),
                reply_markup=cities_keyboard(cities=cities,
                                             func='country_choose'),
                parse_mode='HTML')


async def another_location(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.callback_query.message.reply_text(
        'Отправь мне свою геолокацию или напиши свой '
        'город в формате "Страна, Город, Область/штат(по желанию)".',
    )

    return LOCATION


async def country_choose(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Сохраняет данные пользователя."""
    query = update.callback_query
    lat, lon, place_type = query.data[14:].split('$')
    params = [
        ('lat', lat),
        ('lon', lon),
        ('format', 'json'),
    ]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://nominatim.openstreetmap.org/reverse',
            params=params,
            headers=OSM_HEADERS
        ) as resp:
            place = await resp.json()
            if 'city' in place['address']:
                city = place['address']['city']
            elif place_type in place['address']:
                city = place['address'][place_type]
            else:
                city = place['address']['state']
            country = place['address']['country']

            context.user_data['city'] = city
            context.user_data['country'] = country
            logger.info(f'{city}, {country}')

    await TelegramUser.add_telegram_user(
        telegram_id=context.user_data['telegram_id'],
        chat_id=context.user_data['chat_id'],
        name=context.user_data['name'],
        age=context.user_data['age'],
        bio=context.user_data['bio'],
        city=context.user_data['city'],
        country=context.user_data['country'],
        city_lat=lat,
        city_lon=lon
        )
    await query.message.reply_text(
        'Спасибо, теперь твой профиль заполнен. '
        'Для добавления путешествий перейди в /menu')

    return ConversationHandler.END


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Вывод собранной информации и завершение разговора."""
    await update.message.reply_text(
            "Ошибка в работе бота.")
    return ConversationHandler.END


def main_menu_keyboard():
    keyboard = [
      [InlineKeyboardButton(
          'Мои путешествия 🌴', callback_data='trips')],
      [InlineKeyboardButton(
          'Добавить путешествие 🛫', callback_data='create_trip')],
      [InlineKeyboardButton(
          'Профиль 👫', callback_data='profile')]
    ]
    return InlineKeyboardMarkup(keyboard)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_db = await TelegramUser.get_telegram_user(telegram_id=user.id)
    if not user_db:
        await update.message.reply_text(
            'Для начала необходимо зарегестрироваться, '
            'используйте для этого команду /start'
        )
    else:
        await update.message.reply_text('Выберите, куда вы хотите перейти:',
                                        reply_markup=main_menu_keyboard())


async def main_menu1(update: Update, context):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_db = await TelegramUser.get_telegram_user(telegram_id=user.id)
    if not user_db:
        await query.message.reply_text(
            'Для начала необходимо зарегестрироваться, '
            'используйте для этого команду /start'
        )
    else:
        await query.message.edit_text('Выберите, куда вы хотите перейти:',
                                      reply_markup=main_menu_keyboard())


def trips_keyboard(trip_id: int, is_org: bool):
    keyboard = []
    if is_org:
        keyboard += [
            [InlineKeyboardButton('Добавить участника 🙆‍♂️',
                                  callback_data=f'trip_add_member{trip_id}')]]
    keyboard += [
      [InlineKeyboardButton('Локации 🏔',
                            callback_data=f'trip_locations{trip_id}')],
      [InlineKeyboardButton('Маршрут путешествия 📜',
                            callback_data=f'trip_route{trip_id}')]]
    if is_org:
        keyboard += [
            [InlineKeyboardButton('Изменить путешествие 🛠',
                                  callback_data=f'trip_patch{trip_id}')],
            [InlineKeyboardButton('Удалить путешествие 🗑',
                                  callback_data=f'trip_del{trip_id}')]]
    else:
        keyboard += [
            [InlineKeyboardButton('Выйти из путешествия 🚪',
                                  callback_data=f'trip_del{trip_id}')]]

    return InlineKeyboardMarkup(keyboard)


def location_keyboard(location_id: int, is_org: bool):
    keyboard = [
      [InlineKeyboardButton('Узнать о локации 👓',
                            callback_data=f'location_learn{location_id}')],
      [InlineKeyboardButton('Узнать погоду 🏖',
                            callback_data=f'location_weather{location_id}')],
      [InlineKeyboardButton('Где поесть 🍕',
                            callback_data=f'location_eat{location_id}')],
      [InlineKeyboardButton('Отели рядом 🏠',
                            callback_data=f'location_hotels{location_id}')],
      [InlineKeyboardButton('Заметки 📒',
                            callback_data=f'location_notes{location_id}')],
      [InlineKeyboardButton('Добавить заметку 📝',
                            callback_data=f'trip_add_note{location_id}')],
      [InlineKeyboardButton(
            'Билеты на самолет 💳',
            callback_data=f'location_plane_tickets{location_id}')],
      [InlineKeyboardButton(
            'Билеты на поезд 💳',
            callback_data=f'location_train_tickets{location_id}')],
      ]
    if is_org:
        keyboard += [
            [InlineKeyboardButton(
                'Удалить локацию 🗑',
                callback_data=f'location_delete{location_id}')]]

    return InlineKeyboardMarkup(keyboard)


async def location_notes(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[14:])
    user_id = query.from_user.id

    notes = await Note.get_notes(location_id=location_id)
    notes_available = []

    for note in notes:
        if note.is_public == 1:
            notes_available.append(note)
        else:
            if note.user_id == user_id:
                notes_available.append(note)

    if len(notes_available) == 0:
        await query.message.reply_text(
            'Нет доступных заметок.'
        )
        return
    note_number = 1
    for note in notes_available:
        if note.content_type == 'photo':
            await query.message.reply_photo(
                photo=note.file_id, caption=f'Заметка №{note_number}')
        if note.content_type == 'document':
            await query.message.reply_document(
                document=note.file_id, caption=f'Заметка №{note_number}')
        if note.content_type == 'video':
            await query.message.reply_video(
                video=note.file_id, caption=f'Заметка №{note_number}')
        note_number += 1

    await query.message.reply_text('Выберите, куда вы хотите перейти:',
                                   reply_markup=main_menu_keyboard())


async def trip_add_note(update: Update, context):
    query = update.callback_query
    context.user_data['location_id'] = int(query.data[13:])

    await query.message.reply_text(
            'Твой файл будет доступен для всех участников '
            'путешествия? (если только для тебя, то ответь нет)\n'
            'Напиши Да/Нет'
        )

    return TRIP_ADD_NOTE_ASK


async def trip_add_note_ask(update: Update, context):
    ans = update.message.text
    if ans == 'Да':
        context.user_data['is_public'] = 1
    elif ans == 'Нет':
        context.user_data['is_public'] = 0
    else:
        await update.message.reply_text(
            'Напиши только "Да" или "Нет".'
        )
        return TRIP_ADD_NOTE_ASK

    await update.message.reply_text(
            'Отправь мне файл/фото/видео, которые '
            'ты хочешь прикрепить к данной локации.'
        )

    return TRIP_ADD_NOTE_COMPLETE


async def trip_add_note_complete(update: Update, context):
    msg = update.message
    location_id = context.user_data['location_id']
    is_public = context.user_data['is_public']
    user_id = update.effective_user.id

    if msg.document:
        await Note.add_note(
            location_id=location_id,
            file_id=msg.document.file_id,
            content_type='document',
            is_public=is_public,
            user_id=user_id
        )
    elif msg.photo:
        await Note.add_note(
            location_id=location_id,
            file_id=msg.photo[-1].file_id,
            content_type='photo',
            is_public=is_public,
            user_id=user_id
        )
    elif msg.video:
        await Note.add_note(
            location_id=location_id,
            file_id=msg.video.file_id,
            content_type='video',
            is_public=is_public,
            user_id=user_id
        )
    else:
        await update.message.reply_text(
                'Отправь мне файлы или фото, которые '
                'ты хочешь прикрепить к данной локации.'
            )
        return TRIP_ADD_NOTE_COMPLETE

    await update.message.reply_text(
                'Заметка добавлена ✅',
                reply_markup=main_menu_keyboard()
            )

    return ConversationHandler.END


async def trip_locations(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id

    trip_id = int(query.data[14:])
    trip = await Trip.get_trip(trip_id=trip_id)
    org_id = trip.trip_org
    if user_id == org_id:
        is_org = True
    else:
        is_org = False

    locations = await Location.get_locations(trip_id=trip.id)
    location_id = 1
    if len(locations) == 0:
        await query.message.reply_text(
            'Доступных локаций нет.')
    for location in locations:
        start = location.start.strftime("%d/%m/%Y, %H:%M")
        end = location.end.strftime("%d/%m/%Y, %H:%M")
        template = f'Локация №{location_id}. {location.address}.\n'
        template += f'Прибытие: {start}\nОтбытие {end}\n'
        location_id += 1
        await update.callback_query.message.reply_text(
                template,
                reply_markup=location_keyboard(
                    location_id=location.id,
                    is_org=is_org))


async def location_delete(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[15:])

    await Note.delete_notes(location_id=location_id)
    await Location.delete_location(location_id=location_id)

    await query.message.edit_text(
            'Локация успешно удалена.')


def profile_template(user):
    template = f'<b>👤 Твой профиль:</b>\n\n Имя: {user.name}\n '
    template += f'Возраст: {user.age}\n Страна: '
    template += f'{user.country}\n Город: {user.city}\n'
    template += f'О себе: {user.bio}'

    return template


def profile_keyboard(user_id: int):
    keyboard = [
      [InlineKeyboardButton('Изменить имя 🎙',
                            callback_data='change_name')],
      [InlineKeyboardButton('Изменить возраст 📆',
                            callback_data='change_age')],
      [InlineKeyboardButton('Изменить "о себе" 📃',
                            callback_data='change_bio')],
      [InlineKeyboardButton('Изменить локацию 🛣',
                            callback_data='change_location')],
      ]

    return InlineKeyboardMarkup(keyboard)


async def profile(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id

    user = await TelegramUser.get_telegram_user(telegram_id=user_id)

    await query.message.reply_text(
            profile_template(user),
            parse_mode='HTML',
            reply_markup=profile_keyboard(user_id=user_id)
        )


async def change_name(update: Update, context):
    query = update.callback_query

    await query.message.edit_text(
            'Какое будет твое новое имя?'
        )

    return CHANGE_NAME_COMPLETE


async def change_name_complete(update: Update, context):
    name = update.message.text
    user_id = update.effective_user.id

    await TelegramUser.change_name(telegram_id=user_id, name=name)

    user = await TelegramUser.get_telegram_user(telegram_id=user_id)

    await update.message.reply_text(
            profile_template(user),
            parse_mode='HTML',
            reply_markup=profile_keyboard(user_id=user_id)
        )

    return ConversationHandler.END


async def change_bio(update: Update, context):
    query = update.callback_query

    await query.message.edit_text(
            'Какое будет твое новое био?'
        )

    return CHANGE_BIO_COMPLETE


async def change_bio_complete(update: Update, context):
    bio = update.message.text
    user_id = update.effective_user.id

    await TelegramUser.change_bio(telegram_id=user_id, bio=bio)

    user = await TelegramUser.get_telegram_user(telegram_id=user_id)

    await update.message.reply_text(
            profile_template(user),
            parse_mode='HTML',
            reply_markup=profile_keyboard(user_id=user_id)
        )

    return ConversationHandler.END


async def change_age(update: Update, context):
    query = update.callback_query

    await query.message.edit_text(
            'Какое будет твой новый возраст?'
        )

    return CHANGE_AGE_COMPLETE


async def change_age_complete(update: Update, context):
    age = update.message.text
    user_id = update.effective_user.id

    for number in age:
        if not number.isdigit():
            await update.message.reply_text(
                'Напиши свой настоящий возраст ^_^ e.g. 13',
            )
            return CHANGE_AGE_COMPLETE
    age = int(age)
    if age < 3 or age > 150:
        await update.message.reply_text(
            'Напиши свой настоящий возраст ^_^ e.g. 13',
        )
        return CHANGE_AGE_COMPLETE

    await TelegramUser.change_age(telegram_id=user_id, age=age)

    user = await TelegramUser.get_telegram_user(telegram_id=user_id)

    await update.message.reply_text(
            profile_template(user),
            parse_mode='HTML',
            reply_markup=profile_keyboard(user_id=user_id)
        )

    return ConversationHandler.END


async def change_location(update: Update, context):
    query = update.callback_query

    await query.message.reply_text(
        'Напиши свой '
        'город в формате "Страна, Город, Область/штат(по желанию)".',
    )

    return CHANGE_LOCATION_COMPLETE


async def another_change_location(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.callback_query.message.reply_text(
        'напиши свой '
        'город в формате "Страна, Город, Область/штат(по желанию)".',
    )
    return CHANGE_LOCATION_COMPLETE


async def change_location_choose(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Сохраняет данные локации."""
    query = update.callback_query
    user_id = query.from_user.id
    lat, lon, place_type = query.data[14:].split('$')

    params = [
        ('lat', lat),
        ('lon', lon),
        ('format', 'json'),
    ]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://nominatim.openstreetmap.org/reverse',
            params=params,
            headers=OSM_HEADERS
        ) as resp:
            place = await resp.json()
            if 'city' in place['address']:
                city = place['address']['city']
            elif place_type in place['address']:
                city = place['address'][place_type]
            else:
                city = place['address']['state']
            country = place['address']['country']

            context.user_data['city'] = city
            context.user_data['country'] = country
            logger.info(f'{city}, {country}')

    await TelegramUser.change_location(
        telegram_id=user_id,
        city=context.user_data['city'],
        country=context.user_data['country'],
        city_lat=lat,
        city_lon=lon
        )

    user = await TelegramUser.get_telegram_user(telegram_id=user_id)

    await query.message.delete()

    await query.message.reply_text(
            profile_template(user),
            parse_mode='HTML',
            reply_markup=profile_keyboard(user_id=user_id)
        )
    return ConversationHandler.END


async def change_location_complete(update: Update, context):
    msg = update.message.text.split(', ')
    if len(msg) not in [2, 3]:
        await update.message.reply_text('Неверный формат, попробуйте снова.')
        return CHANGE_LOCATION_COMPLETE
    params = [
        ('country', msg[0]),
        ('city', msg[1]),
        ('format', 'json'),
        ('addressdetails', 1),
        ('limit', 10)
    ]
    if len(msg) == 3:
        params += [('state', msg[2])]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://nominatim.openstreetmap.org/search',
            params=params,
            headers=OSM_HEADERS
        ) as resp:
            cities = await resp.json()
            logger.info(cities)

            if len(cities) == 0:
                await update.message.reply_text(
                    'Город не найден, попробуем найти его снова. '
                    'Отправь мне свою геолокацию или напиши свой '
                    'город в формате "Страна, Город, '
                    'Область/штат(по желанию)".',
                )

                return CHANGE_LOCATION_COMPLETE

            await update.message.reply_text(
                cities_template(cities=cities),
                reply_markup=cities_keyboard(cities=cities,
                                             func='country_choose'),
                parse_mode='HTML')


def trips_template(trip, owner_name, locations):
    template = f'<u>Путешествие №{trip.id}</u>\n\n <b>Название: {trip.name}\n '
    template += f'Описание: {trip.description}\n Организатор: '
    template += f'{owner_name}\n Локации:</b>\n'
    location_id = 1
    for location in locations:
        start = location.start.strftime("%d/%m/%Y, %H:%M")
        end = location.end.strftime("%d/%m/%Y, %H:%M")
        template += f'<i>№{location_id}. {location.address}.\n'
        template += f'Прибытие: {start}\nОтбытие {end}</i>\n'
        location_id += 1
    return template


async def trips_list(update: Update, context):
    query = update.callback_query
    logger.info(query)

    user_id = query.from_user.id
    user_trips = await UserTrip.get_user_trips(user_id=user_id)

    if len(user_trips) == 0:
        await query.message.reply_text(
            'На данный момент у вас нет никаких '
            'путешествий, чтобы их добавить нажмите "Добавить путешествие 🛫"',
            reply_markup=main_menu_keyboard())

    for user_trip in user_trips:
        trip = await Trip.get_trip(trip_id=user_trip.trip)
        org_id = trip.trip_org
        org = await TelegramUser.get_telegram_user(telegram_id=org_id)
        if user_id == org_id:
            is_org = True
        else:
            is_org = False
        locations = await Location.get_locations(trip_id=trip.id)
        await query.message.reply_text(
            trips_template(trip, org.name, locations),
            parse_mode='HTML',
            reply_markup=trips_keyboard(trip_id=trip.id, is_org=is_org))


async def trip_route(update: Update, context):
    query = update.callback_query
    await query.answer()

    trip_id = int(query.data[10:])
    user_id = query.from_user.id
    trip = await Trip.get_trip(trip_id=trip_id)

    org_id = trip.trip_org
    org = await TelegramUser.get_telegram_user(telegram_id=org_id)
    user = await TelegramUser.get_telegram_user(telegram_id=user_id)
    locations = await Location.get_locations(trip_id=trip_id)

    if user_id == org_id:
        is_org = True
    else:
        is_org = False

    await update.callback_query.message.reply_text(
        'Ожидайте, идет загрузка...\n'
        '(Маршрут будет построен от вашего города)',
    )

    places = [(user.city_lat, user.city_lon)]

    for location in locations:
        places.append((location.location_lat, location.location_lon))

    if len(places) == 1:
        await query.message.reply_text(
            'Слишком мало локаций.',
            reply_markup=main_menu_keyboard())

    route = Route()
    photo = await route.build_routes(places=places)
    if photo == 0:
        await query.message.edit_text(
            'Невозможно построить маршрут между разными континентами.',
            reply_markup=main_menu_keyboard())
    else:
        await query.message.reply_photo(
            photo=photo,
            caption=trips_template(trip, org.name, locations),
            parse_mode='HTML',
            reply_markup=trips_keyboard(trip_id=trip.id, is_org=is_org)
        )


async def trip_delete(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    trip_id = int(query.data[8:])

    trip = await Trip.get_trip(trip_id=trip_id)

    if trip.trip_org != query.from_user.id:
        locations = await Location.get_locations(trip_id=trip_id)
        for location in locations:
            await Note.delete_notes_user(
                location_id=location.id, user_id=user_id)
        await UserTrip.delete_user_trip(
            trip_id=trip_id, user=query.from_user.id)
        await update.callback_query.message.edit_text(
            'Вы вышли из путешествия.')
    else:
        locations = await Location.get_locations(trip_id=trip_id)
        for location in locations:
            await Note.delete_notes(location_id=location.id)

        await Location.delete_locations(trip_id=trip_id)
        await UserTrip.delete_user_trips(trip_id=trip_id)
        await Trip.delete_trip(trip_id=trip_id)

        await update.callback_query.message.edit_text(
            'Путешествие успешно удалено.')


def trip_patch_keyboard(trip_id: int):
    keyboard = [
      [InlineKeyboardButton('Изменить название 🔍',
                            callback_data=f'trip_patch_name{trip_id}')],
      [InlineKeyboardButton('Изменить описание 📗',
                            callback_data=f'trip_patch_bio{trip_id}')],
      [InlineKeyboardButton('Добавить локацию 🏕',
                            callback_data=f'trip_add_location{trip_id}')]]

    return InlineKeyboardMarkup(keyboard)


async def trip_patch(update: Update, context):
    query = update.callback_query
    trip_id = int(query.data[10:])

    await query.message.reply_text(
            'Выберите действие:',
            reply_markup=trip_patch_keyboard(trip_id=trip_id))


async def trip_patch_name(update: Update, context):
    query = update.callback_query
    context.user_data['trip_id'] = int(query.data[15:])

    await query.message.reply_text(
            'Какое будет новое название у поездки?'
        )

    return TRIP_PATCH_NAME_COMPLETE


async def trip_patch_name_complete(update: Update, context):
    trip_id = int(context.user_data['trip_id'])
    trip_name = update.message.text

    await Trip.change_name(
        trip_id=trip_id,
        trip_name=trip_name)

    trip = await Trip.get_trip(trip_id=trip_id)

    locations = await Location.get_locations(trip_id=trip.id)
    org_id = trip.trip_org
    org = await TelegramUser.get_telegram_user(telegram_id=org_id)
    await update.message.reply_text(
        trips_template(trip, org.name, locations),
        parse_mode='HTML',
        reply_markup=trips_keyboard(trip_id=trip.id, is_org=True))

    return ConversationHandler.END


async def trip_patch_bio(update: Update, context):
    query = update.callback_query
    context.user_data['trip_id'] = int(query.data[14:])

    await query.message.reply_text(
            'Какое будет новое описание у поездки?'
        )

    return TRIP_PATCH_BIO_COMPLETE


async def trip_patch_bio_complete(update: Update, context):
    trip_id = context.user_data['trip_id']
    trip_bio = update.message.text

    await Trip.change_bio(
        trip_id=trip_id,
        description=trip_bio)

    trip = await Trip.get_trip(trip_id=trip_id)

    locations = await Location.get_locations(trip_id=trip.id)
    org_id = trip.trip_org
    org = await TelegramUser.get_telegram_user(telegram_id=org_id)
    await update.message.reply_text(
        trips_template(trip, org.name, locations),
        parse_mode='HTML',
        reply_markup=trips_keyboard(trip_id=trip.id, is_org=True))

    return ConversationHandler.END


async def trip_add_location(update: Update, context):
    query = update.callback_query
    context.user_data['trip_id'] = int(query.data[17:])

    await query.message.reply_text(
        'Напиши мне информацию про локацию '
        'в таком формате:\n'
        '<b>Название локации + дата и время прибытия в нее '
        '+ дата и время отбытия из нее</b>\n'
        '<i>e.g Музей восковых фигур в Питере '
        '25.04.2024 9:00 27.04.2024 13:30</i>',
        parse_mode='HTML',
    )
    return TRIP_ADD_LOCATION_COMPLETE


async def another_trip_add_location(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.callback_query.message.reply_text(
        'Попробуй уточнить локацию: например, '
        'добавь название страны или города.',
    )

    return TRIP_ADD_LOCATION_COMPLETE


async def trip_add_location_choose(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Сохраняет данные локации."""
    query = update.callback_query
    lat, lon, place_type = query.data[15:].split('$')
    inf = context.user_data['last']

    logger.info([lat, lon, inf])
    await Location.add_location(
                address=inf[0],
                trip_id=inf[3],
                start=inf[1],
                end=inf[2],
                location_lon=lon,
                location_lat=lat
            )

    trip = await Trip.get_trip(trip_id=inf[3])
    locations = await Location.get_locations(trip_id=trip.id)
    org_id = trip.trip_org
    org = await TelegramUser.get_telegram_user(telegram_id=org_id)

    await query.message.delete()

    await query.message.reply_text(
        trips_template(trip, org.name, locations),
        parse_mode='HTML',
        reply_markup=trips_keyboard(trip_id=trip.id, is_org=True))

    return ConversationHandler.END


async def trip_add_location_complete(update: Update, context):
    trip_id = context.user_data['trip_id']

    info = update.message.text

    response = validate_location(info=info)
    if type(response) == str:
        await update.message.reply_text(
                response,
            )
        return TRIP_ADD_LOCATION_COMPLETE

    address = response[0]
    date_arrive = response[1]
    date_departure = response[2]

    params = [
        ('q', address),
        ('format', 'json'),
        ('addressdetails', 1),
        ('limit', 10)
    ]

    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://nominatim.openstreetmap.org/search',
            params=params,
            headers=OSM_HEADERS
        ) as resp:
            locations = await resp.json()
            logger.info(locations)

            if len(locations) == 0:
                await update.message.reply_text(
                    'Место не найдено, попробуем найти его снова. '
                    'Добавь к адресу название города или области. '
                )

                return TRIP_ADD_LOCATION_COMPLETE

            context.user_data['last'] = (
                address, date_arrive, date_departure, trip_id)

            await update.message.reply_text(
                cities_template(cities=locations),
                reply_markup=cities_keyboard(cities=locations,
                                             func='location_choose'),
                parse_mode='HTML')


async def trip_add_member(update: Update, context):
    query = update.callback_query
    trip_id = int(query.data[15:])
    trip = await Trip.get_trip(trip_id=trip_id)
    if trip.trip_org != query.from_user.id:
        await update.callback_query.message.reply_text(
            'Пригласить в поездку может только организатор.'
        )
    else:
        token = await Invite.add_invite(trip_id=trip_id)
        await update.callback_query.message.reply_text(
            'Пришли эту одноразовую ссылку другу. Важно, '
            'чтобы он был зарегистрирован в боте:')
        await update.callback_query.message.reply_text(
            f'https://t.me/HTTravelMateBot?start={token}'
        )


async def trip_create(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text('Как будет называться твое путешествие?')

    return TRIP_NAME


async def trip_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос информации о выбранном предопределенном выборе."""
    name = update.message.text
    context.user_data.clear()

    trip = await Trip.get_trip_by_name(trip_name=name)
    if trip:
        await update.message.reply_text(
            'Такое название поездки уже существует, придумай другое',
        )
        return TRIP_NAME

    context.user_data['trip_name'] = name

    await update.message.reply_text(
        'Теперь добавь описание к путешествию',
    )
    return TRIP_BIO


async def trip_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос информации о выбранном предопределенном выборе."""
    bio = update.message.text

    await update.message.reply_text(
        'Сколько различных локаций ты планируешь посетить? '
        'Не переживай, если не не укажешь все места, их можно будет добавить.',
    )
    context.user_data['trip_bio'] = bio

    return TRIP_HM


async def trip_hm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Запрос информации о выбранном предопределенном выборе."""
    numb = update.message.text

    for number in numb:
        if not number.isdigit():
            await update.message.reply_text(
                'Напиши настоящее количество.',
            )
            return TRIP_HM

    numb = int(numb)
    if numb < 1 or numb > 20:
        await update.message.reply_text(
            'Напиши настоящее количество.',
        )
        return TRIP_HM

    context.user_data['trip_locations_count'] = numb
    context.user_data['trip_locations_number'] = 1
    context.user_data['trip_locations'] = []

    await update.message.reply_text(
        'Напиши мне информацию про локацию №1 в таком формате:\n'
        '<b>Название локации/адрес + дата и время прибытия в нее '
        '+ дата и время отбытия из нее</b>\n'
        '<i>e.g Колизей 25.04.2024 9:00 27.04.2024 13:30</i>',
        parse_mode='HTML',
    )
    return TRIP_LOCATION


def validate_location(
    info,
):
    """Валидация."""

    info_parsed = info.split(' ')

    if len(info_parsed) < 5:
        return LOCATION_WRONG_FORMAT

    address = ' '.join(info_parsed[:-4])
    date1 = info_parsed[-4]
    time1 = info_parsed[-3]
    date2 = info_parsed[-2]
    time2 = info_parsed[-1]

    d1 = list(find_dates(date1))
    if len(d1) != 1:
        return LOCATION_WRONG_FIRST_DATE

    d2 = list(find_dates(date2))
    if d2 is None:
        return LOCATION_WRONG_SECOND_DATE

    if len(time1.split(':')) != 2:
        return LOCATION_WRONG_FIRST_TIME
    hrs1, min1 = time1.split(':')
    if len(hrs1) > 2:
        return LOCATION_WRONG_FIRST_TIME
    for number in hrs1:
        if not number.isdigit():
            return LOCATION_WRONG_FIRST_TIME
    if len(min1) > 2:
        return LOCATION_WRONG_FIRST_TIME
    for number in min1:
        if not number.isdigit():
            return LOCATION_WRONG_FIRST_TIME
    hrs1 = int(hrs1)
    min1 = int(min1)
    if hrs1 > 24 or hrs1 < 0 or min1 < 0 or min1 > 60:
        return LOCATION_WRONG_FIRST_TIME

    if len(time2.split(':')) != 2:
        return LOCATION_WRONG_SECOND_TIME
    hrs2, min2 = time2.split(':')
    if len(hrs2) > 2:
        return LOCATION_WRONG_SECOND_TIME
    for number in hrs2:
        if not number.isdigit():
            return LOCATION_WRONG_SECOND_TIME
    if len(min2) > 2:
        return LOCATION_WRONG_SECOND_TIME
    for number in min2:
        if not number.isdigit():
            return LOCATION_WRONG_SECOND_TIME
    hrs2 = int(hrs2)
    min2 = int(min2)
    if hrs2 > 24 or hrs2 < 0 or min2 < 0 or min2 > 60:
        return LOCATION_WRONG_SECOND_TIME

    date_arrive = d1[0] + timedelta(hours=hrs1, minutes=min1)
    date_departure = d2[0] + timedelta(hours=hrs2, minutes=min2)

    return [address, date_arrive, date_departure]


async def another_trip_location(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.callback_query.message.reply_text(
        'Попробуй уточнить локацию: например, '
        'добавь название страны или города.',
    )

    return TRIP_LOCATION


async def location_choose(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Сохраняет данные локации."""
    query = update.callback_query
    lat, lon, place_type = query.data[15:].split('$')
    inf = context.user_data['last']
    address = inf[0]
    date_arrive = inf[1]
    date_departure = inf[2]

    context.user_data['trip_locations'] += [(
        lat, lon, address, date_arrive, date_departure)
    ]
    await query.message.delete()
    location_number = context.user_data['trip_locations_number']
    if context.user_data['trip_locations_count'] == location_number:
        trip = await Trip.add_trip(
            name=context.user_data['trip_name'],
            description=context.user_data['trip_bio'],
            trip_org=update.effective_user.id
            )
        logger.info(context.user_data['trip_locations'])
        for location in context.user_data['trip_locations']:
            await Location.add_location(
                address=location[2],
                trip_id=trip.id,
                start=location[3],
                end=location[4],
                location_lon=location[1],
                location_lat=location[0]
            )

        await query.message.reply_text(
         'Путешествие успешно добавлено', reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    context.user_data['trip_locations_number'] += 1
    location_number = context.user_data['trip_locations_number']

    await query.message.reply_text(
        f'Напиши мне информацию про локацию №{location_number} '
        'в таком формате:\n'
        '<b>Название локации + дата и время прибытия в нее '
        '+ дата и время отбытия из нее</b>\n'
        '<i>e.g Колизей 25.04.2024 9:00 27.04.2024 13:30</i>',
        parse_mode='HTML',
    )
    return TRIP_LOCATION


async def trip_location(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Запрос информации о выбранном предопределенном выборе."""
    info = update.message.text

    response = validate_location(info=info)
    if type(response) == str:
        await update.message.reply_text(
                response,
            )
        return TRIP_LOCATION

    address = response[0]
    date_arrive = response[1]
    date_departure = response[2]

    params = [
        ('q', address),
        ('format', 'json'),
        ('addressdetails', 1),
        ('limit', 10)
    ]

    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://nominatim.openstreetmap.org/search',
            params=params,
            headers=OSM_HEADERS
        ) as resp:
            locations = await resp.json()
            logger.info(locations)

            if len(locations) == 0:
                await update.message.reply_text(
                    'Место не найдено, попробуем найти его снова. '
                    'Добавь к адресу название города или области. '
                )

                return TRIP_LOCATION

            context.user_data['last'] = (address, date_arrive, date_departure)

            await update.message.reply_text(
                cities_template(cities=locations),
                reply_markup=cities_keyboard(cities=locations,
                                             func='location_choose'),
                parse_mode='HTML')


async def location_learn(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[14:])
    location = await Location.get_location(location_id=location_id)
    location_name = location.address
    await update.callback_query.message.edit_text(
        'Ожидайте, идет загрузка...'
    )
    data = {
        'modelUri': 'gpt://b1g2ahktcv1255vqabvd/yandexgpt',
        'messages': [
            {
                'text': 'Ты туристический гид, '
                'дай ответ менее, чем в 600 символов',
                'role': 'system'
            },
            {
                'text': f'Расскажи про {location_name} '
                'и достопримечательности оттуда',
                'role': 'user'
            }
        ],
        'completionOptions': {
            'stream': False,
            'maxTokens': 200,
            'temperature': 0.3
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
            json=data,
            headers=YANDEX_HEADERS
        ) as resp:
            await update.callback_query.message.delete()
            response = await resp.json()
            message = response['result']['alternatives'][0]['message']['text']
            await update.callback_query.message.reply_text(
                message, reply_markup=main_menu_keyboard()
            )


def location_weather_template(daily):
    template = 'Погода по дням:\n'
    time = len(daily['time'])
    for day in range(time):
        date = daily['time'][day]
        max_temp = daily['temperature_2m_max'][day]
        min_temp = daily['temperature_2m_min'][day]

        template += f' - Погода на {date}:\n'
        template += f'   Макс. температура: {max_temp}\n'
        template += f'   Мин. температура: {min_temp}\n'

        if daily['rain_sum'][day] > 0:
            template += '   Возможны дожди!\n'
        if daily['snowfall_sum'][day] > 0:
            template += '   Возможен снегопад!\n'
        template += '\n'
    return template


async def location_weather(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[16:])
    location = await Location.get_location(location_id=location_id)

    params = [
        ('latitude', location.location_lat),
        ('longitude', location.location_lon),
        ('start_date', location.start.strftime("%Y-%m-%d")),
        ('end_date', location.end.strftime("%Y-%m-%d")),
        ('daily', 'temperature_2m_max'),
        ('daily', 'temperature_2m_min'),
        ('daily', 'rain_sum'),
        ('daily', 'snowfall_sum'),
    ]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://api.open-meteo.com/v1/forecast',
            params=params,
        ) as resp:
            response = await resp.json()
            logger.info(response)
            if 'error' in response:
                await query.message.edit_text(
                    'Мы не можем сделать прогноз на эти даты.')
                return
            daily = response['daily']

            await query.message.edit_text(
                location_weather_template(daily=daily),
                reply_markup=main_menu_keyboard()
            )


def location_restraunts_template(restraunts):
    template = 'Рестораны и кафе рядом:\n'
    for restraunt in restraunts:
        if 'rating' in restraunt and 'name' in restraunt and \
           'address' in restraunt['location']:
            restraunt_name = restraunt['name']
            restraunt_rating = restraunt['rating']
            restraunt_address = restraunt['location']['address']

            template += f' - {restraunt_name}\n'
            template += f'    Рейтинг: {restraunt_rating}\n'
            template += f'    Адрес: {restraunt_address}\n'
            template += '\n'
    if template == 'Рестораны и кафе рядом:\n':
        template = 'Рядом с локацией нет ресторанов и кафе.'

    return template


async def location_eat(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[12:])
    location = await Location.get_location(location_id=location_id)
    cords = f'{location.location_lat},{location.location_lon}'

    params = [
        ('query', 'ресторан+кафе+restaurant+cafe'),
        ('ll', cords),
        ('sort', 'RELEVANCE'),
        ('radius', 10000),
        ('fields', 'name,location,rating')
    ]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://api.foursquare.com/v3/places/search',
            params=params,
            headers=FSQ_HEADERS
        ) as resp:
            response = await resp.json()
            logger.info(response)
            restraunts = response['results']

            await query.message.edit_text(
                location_restraunts_template(restraunts=restraunts),
                reply_markup=main_menu_keyboard()
            )


def location_hotels_template(hotels):
    template = 'Отели рядом:\n'
    for hotel in hotels:
        if 'rating' in hotel and 'website' in hotel and \
           'address' in hotel['location']:
            hotel_name = hotel['name']
            hotel_rating = hotel['rating']
            hotel_website = hotel['website']
            hotel_address = hotel['location']['address']

            template += f' - {hotel_name}\n'
            template += f'    Рейтинг: {hotel_rating}\n'
            template += f'    Сайт: {hotel_website}\n'
            template += f'    Адрес: {hotel_address}\n'
            template += '\n'
    if template == 'Отели рядом:\n':
        template = 'Рядом с локацией нет отелей.'
    return template


async def location_hotels(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[15:])
    location = await Location.get_location(location_id=location_id)
    cords = f'{location.location_lat},{location.location_lon}'
    params = [
        ('query', 'hotel'),
        ('ll', cords),
        ('sort', 'RELEVANCE'),
        ('radius', 8000),
        ('fields', 'name,location,website,rating')
    ]

    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://api.foursquare.com/v3/places/search',
            params=params,
            headers=FSQ_HEADERS
        ) as resp:
            response = await resp.json()
            logger.info(response)
            hotels = response['results']

            await query.message.edit_text(
                location_hotels_template(hotels=hotels),
                reply_markup=main_menu_keyboard()
            )


def location_plane_tickets_template(plane_tickets):
    template = 'Билеты на самолет:\n'
    num = 1
    for ticket in plane_tickets[:10]:
        price = ticket[0]
        company = ticket[1][0]['company']
        dep_name = ticket[1][0]['dep_name']
        arr_name = ticket[1][0]['arr_name']
        dep_code = ticket[1][0]['dep_code']
        arr_code = ticket[1][0]['arr_code']
        dep_time = ticket[1][0]['dep_time']
        arr_time = ticket[1][0]['arr_time']
        link = ticket[2]
        template += f'Вариант №{num}\n'
        template += f'   Цена: {price} руб.\n'
        template += f'   Авиакомпания: {company}\n'
        template += f'   Отправление: {dep_name}, {dep_code}, {dep_time}\n'
        template += f'   Прибытие: {arr_name}, {arr_code}, {arr_time}\n'
        template += f'   Купить: {link}\n'
        template += '\n'
        num += 1
    if template == 'Билеты на самолет:\n':
        template = 'Билеты не самолет найдены.'
    return template


def location_train_tickets_template(train_tickets):
    template = 'Билеты на поезд:\n'
    num = 1
    for ticket in train_tickets[:3]:
        train_number = ticket[0]
        dest_st = ticket[1]
        fin_st = ticket[2]
        dep_time = ticket[3]
        arr_time = ticket[4]

        template += f'Вариант №{num}\n'
        template += f'   Номер поезда: {train_number}\n'
        template += f'   Отправление: {dest_st}, {dep_time}\n'
        template += f'   Прибытие: {fin_st}, {arr_time}\n'
        for seat in ticket[5][:5]:
            price = seat[0]
            service = seat[1]
            template += f'   Тип места: {service}\n'
            template += f'   Цена: {price} руб.\n'
        template += '\n'
        num += 1
    if template == 'Билеты на поезд:\n':
        template = 'Билеты на поезд не найдены.'
    return template


async def location_plane_tickets(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[22:])
    user_id = query.from_user.id
    user = await TelegramUser.get_telegram_user(telegram_id=user_id)
    location = await Location.get_location(location_id=location_id)

    await update.callback_query.message.reply_text(
        'Ожидайте, идет загрузка...\n'
    )

    headers = {
                "User-Agent": faker.Faker().chrome(),
                "Content-Type": "application/json",
                "Accept-Language": "ru",
            }
    async with aiohttp.ClientSession() as session:
        params = [
            ('str', user.city),
            ('limit', 1),
        ]
        async with session.get(
            'https://hinter.kupibilet.ru/hinter.json?',
            params=params,
            headers=headers
        ) as resp:
            response = await resp.json()
            city_code = response['data']

            if not city_code:
                await query.message.edit_text(
                    'В вашем городе нет аэропорта, '
                    'выберите другой город в профиле.'
                )
                city_code = 'ZZZ'
            else:
                city_code = city_code[0]["city"]["code"]
            logger.info(f'city_code: {city_code}')
        params = [
            ('str', location.address),
            ('limit', 1),
        ]
        async with session.get(
            'https://hinter.kupibilet.ru/hinter.json?',
            params=params,
            headers=headers
        ) as resp:
            response = await resp.json()
            to_code = response['data']

            if not to_code:
                await query.message.edit_text(
                    'Название/адрес локации должны быть городом, '
                    'в котором есть аэропорт.'
                )
                to_code = 'ZZZ'
            else:
                to_code = to_code[0]["city"]["code"]
        data = {
                "trips": [
                    {
                        "arrival": to_code,
                        "departure": city_code,
                        "date": location.start.strftime('%Y-%m-%d')
                    }
                ],
                "travelers": {
                    "adult": 1,
                    "child": 0,
                    "infant": 0
                },
                "cabin": "economy",
                "agent": "context_nb",
                "language": "RU",
                "currency": "RUB",
                "client_platform": "web"
            }
        headers = {
                "User-Agent": faker.Faker().chrome(),
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Language": "ru",
            }

        async with session.post(
            'https://api-rs.kupibilet.ru/frontend_search',
            json=data,
            headers=headers
        ) as resp:
            result = await resp.json()
            logger.info('api reached #1')
            tickets = []
            variants = result["variants"]
            flights = result["flights"]
            airports = result["anyports"]
            cities = result["cities"]
            if len(variants) > 11:
                variants = variants[:10]
                logger.info('api check #1')
            for variant in variants:
                price = variant["price"]["amount"]
                segments = []
                for flight_id in variant["segments"][0]["flights"]:
                    flight = flights[flight_id]

                    dep_code = flight["departure"]
                    dep_name = cities[airports[dep_code]["city_code"]]["name"]
                    dep_time = flight["departure_datetime"]

                    arr_code = flight["arrival"]
                    arr_name = cities[airports[arr_code]["city_code"]]["name"]
                    arr_time = flight["arrival_datetime"]

                    company = result["airlines"][
                        flight["operating_carrier"]]["name"]

                    segments.append({
                        'company': company,
                        'dep_name': dep_name,
                        'arr_name': arr_name,
                        'dep_code': dep_code,
                        'arr_code': arr_code,
                        'dep_time': dep_time,
                        'arr_time': arr_time
                    })
                id = variant["id"]
                tickets.append([
                    price,
                    segments,
                    f"https://kupibilet.ru/mbooking/step0/{id}"
                ])

            await query.message.reply_text(
                    location_plane_tickets_template(plane_tickets=tickets),
                    reply_markup=main_menu_keyboard()
                )


async def location_train_tickets(update: Update, context):
    query = update.callback_query
    location_id = int(query.data[22:])
    user_id = query.from_user.id
    user = await TelegramUser.get_telegram_user(telegram_id=user_id)
    location = await Location.get_location(location_id=location_id)

    await update.callback_query.message.reply_text(
        'Ожидайте, идет загрузка...\n'
    )

    async with aiohttp.ClientSession() as session:
        headers = {
                "User-Agent": faker.Faker().chrome(),
                "Content-Type": "application/json",
                "Accept-Language": "ru",
            }
        params = [
                    ('GroupResults', 'true'),
                    ('RailwaySortPriority', 'true'),
                    ('MergeSuburban', 'true'),
                    ('Query', user.city),
                    ('TransportType', 'rail'),
                    ('Language', 'ru'),
                ]
        logger.info('api start rzd')
        async with session.get(
                'https://ticket.rzd.ru/api/v1/suggests',
                params=params,
                headers=headers
        ) as resp:

            response = await resp.json(content_type=None)
            city_from = 'abcs'
            if 'city' not in response:
                await query.message.reply_text(
                            'В вашем городе нет жд станций, '
                            'выберите другой город в профиле.'
                        )
            else:
                city_from = response['city'][0]['expressCode']

        params = [
                    ('GroupResults', 'true'),
                    ('RailwaySortPriority', 'true'),
                    ('MergeSuburban', 'true'),
                    ('Query', location.address),
                    ('TransportType', 'rail'),
                    ('Language', 'ru'),
                ]
        async with session.get(
                'https://ticket.rzd.ru/api/v1/suggests',
                params=params,
                headers=headers
        ) as resp:
            city_to = 'abcs'
            response = await resp.json(content_type=None)
            if 'city' not in response:
                await query.message.reply_text(
                        'В локации нет вокзала.'
                    )
            else:
                city_to = response['city'][0]['expressCode']
        logger.info(f'{city_from}: {city_to}')
        start = location.start.strftime('%Y-%m-%dT%H:%M:%S')
        data = {
                    "Origin": str(city_from),
                    "Destination": str(city_to),
                    "DepartureDate": start,
                    "GetTrainsFromSchedule": 'true',
                    "GetByLocalTime": 'true',
                    "CarGrouping": "DontGroup",
                    "CarIssuingType": "All"
                }
        async with session.post(
                'https://ticket.rzd.ru/apib2b/p/Railway'
                '/V1/Search/TrainPricing',
                json=data,
                headers=headers
        ) as resp:
            result = await resp.json(content_type=None)

            if 'Trains' in result:
                trains = result['Trains']
            else:
                trains = []

            train_list = []
            if len(trains) > 6:
                trains = trains[:5]
            for train in trains:
                train_list.append([
                        train['TrainNumber'],
                        train['OriginStationName'],
                        train['FinalStationName'],
                        train['DepartureDateTime'],
                        train['ArrivalDateTime'],
                        [
                            (seat['MinPrice'],
                             seat['CarType']
                             ) for seat in train['CarGroups']]])

        await query.message.reply_text(
                    location_train_tickets_template(train_tickets=train_list),
                    reply_markup=main_menu_keyboard()
                )


def main() -> None:
    application = Application.builder().token(
        os.getenv('TOKEN')
    ).build()

    registration_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, bio)],
            LOCATION: [
                MessageHandler(filters.LOCATION, location),
                CallbackQueryHandler(
                    another_location, pattern='another_location'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_hand),
                CallbackQueryHandler(country_choose, pattern='country_choose')
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )

    create_trip_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            trip_create, pattern='create_trip')],
        states={
            TRIP_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, trip_name)],
            TRIP_BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, trip_bio)],
            TRIP_HM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, trip_hm)],
            TRIP_LOCATION: [
                CallbackQueryHandler(
                    another_trip_location, pattern='another_location'),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, trip_location),
                CallbackQueryHandler(location_choose,
                                     pattern='location_choose')
                ],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )

    patch_name_trip_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            trip_patch_name, pattern='trip_patch_name')],
        states={
            TRIP_PATCH_NAME_COMPLETE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    trip_patch_name_complete)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )
    patch_bio_trip_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            trip_patch_bio, pattern='trip_patch_bio')],
        states={
            TRIP_PATCH_NAME_COMPLETE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    trip_patch_bio_complete)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )
    add_location_trip_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            trip_add_location, pattern='trip_add_location')],
        states={
            TRIP_ADD_LOCATION_COMPLETE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    trip_add_location_complete),
                CallbackQueryHandler(
                    another_trip_add_location, pattern='another_location'),
                CallbackQueryHandler(trip_add_location_choose,
                                     pattern='location_choose')],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )
    change_name_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            change_name, pattern='change_name')],
        states={
            CHANGE_NAME_COMPLETE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    change_name_complete)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )
    change_bio_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            change_bio, pattern='change_bio')],
        states={
            CHANGE_NAME_COMPLETE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    change_bio_complete)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )
    change_age_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            change_age, pattern='change_age')],
        states={
            CHANGE_NAME_COMPLETE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    change_age_complete)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )
    change_location_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            change_location, pattern='change_location')],
        states={
            CHANGE_LOCATION_COMPLETE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    change_location_complete),
                CallbackQueryHandler(
                    another_change_location, pattern='another_location'),
                CallbackQueryHandler(change_location_choose,
                                     pattern='country_choose')],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )
    add_note_trip_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            trip_add_note, pattern='trip_add_note')],
        states={
            TRIP_ADD_NOTE_ASK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    trip_add_note_ask)],
            TRIP_ADD_NOTE_COMPLETE: [
                MessageHandler(
                    (filters.PHOTO | filters.VIDEO | filters.Document.ALL)
                    & ~filters.COMMAND,
                    trip_add_note_complete)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
        allow_reentry=True,
    )

    application.add_handler(registration_handler)
    application.add_handler(create_trip_handler)
    application.add_handler(patch_name_trip_handler)
    application.add_handler(patch_bio_trip_handler)
    application.add_handler(add_location_trip_handler)
    application.add_handler(add_note_trip_handler)
    application.add_handler(change_name_handler)
    application.add_handler(change_bio_handler)
    application.add_handler(change_age_handler)
    application.add_handler(change_location_handler)
    application.add_handler(CommandHandler('menu', main_menu))
    application.add_handler(CallbackQueryHandler(main_menu1, pattern='menu'))
    application.add_handler(CallbackQueryHandler(trips_list, pattern='trips'))
    application.add_handler(CallbackQueryHandler(profile, pattern='profile'))
    application.add_handler(CallbackQueryHandler(
        location_notes, pattern='location_notes'))
    application.add_handler(CallbackQueryHandler(
        trip_locations, pattern='trip_locations'))
    application.add_handler(CallbackQueryHandler(
            trip_add_member, pattern='trip_add_member'))
    application.add_handler(CallbackQueryHandler(
            trip_route, pattern='trip_route'))
    application.add_handler(
        CallbackQueryHandler(location_learn, pattern='location_learn'))
    application.add_handler(
        CallbackQueryHandler(location_weather, pattern='location_weather'))
    application.add_handler(
        CallbackQueryHandler(location_eat, pattern='location_eat'))
    application.add_handler(
        CallbackQueryHandler(location_hotels, pattern='location_hotels'))
    application.add_handler(
        CallbackQueryHandler(location_delete, pattern='location_delete'))
    application.add_handler(
        CallbackQueryHandler(location_plane_tickets,
                             pattern='location_plane_tickets'))
    application.add_handler(
        CallbackQueryHandler(location_train_tickets,
                             pattern='location_train_tickets'))
    application.add_handler(CallbackQueryHandler(
        trip_delete, pattern='trip_del'))
    application.add_handler(CallbackQueryHandler(
        trip_patch, pattern='trip_patch'))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    future1 = asyncio.ensure_future(init_models())
    loop.run_until_complete(future1)
    future2 = asyncio.ensure_future(main())
    loop.run_until_complete(future2)
