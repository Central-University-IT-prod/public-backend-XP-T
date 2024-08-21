# TravelMate
<!-- ABOUT THE PROJECT -->
## О Проекте

TravelMate - это телеграм бот, который способен взять значительную часть задач по организации ваших путешествий на себя.
Он способен создавать различные путешествия, добавлять в них своих друзей, делиться с ними заметками, находить рестораны около локаций, 
где вы планируете остановиться и многое другое. Со всем остальным вы можете ознакомиться в __Работе с ботом__.

<!-- GETTING STARTED -->
## Getting Started

Для начала бота нужно установить либо на компьютере в visual studio code или другом интерпретаторе
или в контейнерах в docker'е. После этого начинается взаимодействие с ботом через телеграм.

### Инструкция по установке

Если вы хотите запустить бота локально:
  1. Скопируйте репозиторий и перейдите в него.
     
     ```sh
     git clone https://github.com/Central-University-IT-prod/backend-XP-T
     cd backend-XP-T
     ```
  3. Создайте в нем .env файл. Ниже показано, как он должен выглядеть:
     
     ```
      TOKEN=secret# указываем токен, который получаем в телеграме у @BotFather

  4. Установите виртуальное окружение:
     
     ```sh
     python3 -m venv venv
     ```
  5. Установите зависимости.
     
     ```sh
     pip3 install -r requirements.txt
     ```
  7. В файле app/core/config.py поменять базу данных с PostgreSQL на SQLite
     Для этого уберите комментарий с 26-ой строчки и закомментируйте 27-ую
  8. Запустите файл app/main.py - Готово!

Как запустить приложение в докере:
### ❗️❗️❗️ ВАЖНО ❗️❗️❗️
__❗️❗️❗️ ВАЖНО ❗️❗️❗️ Сервер, где будет расположен бот, должен находиться на территории России, иначе не будет работать функция "Билеты на поезд 💳"__

docker-compose.yml создает два контейнера: первый для базы данных (db), второй для самого бота (bot).
В обоих контейнера задаются переменные окружения, которые можно изменить в этом же файле. Главное, что 
имеет смысл менять - это TOKEN, необходимый для подключения к вашему боту в телеграм.
1. Скопируйте репозиторий и перейдите в него.
     ```sh
     git clone https://github.com/Central-University-IT-prod/backend-XP-T
     cd backend-XP-T
     ```
2. В docker-compose.yml замените TOKEN бота на свой:
     ```sh
      TOKEN=secret # указываем токен, который получаем в телеграме у @BotFather
    ```
3. Запускаем
   
    ```sh
   docker-compose up -d
    ```



<!-- USAGE EXAMPLES -->
## Работа с ботом
### Регистрация
  ![image](https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/f52bdac0-1f69-41d1-9c14-5234b0b0bb68)

Структура регистрации:
  1. Пользователь нажимает /start
  2. Бот спрашивает и сохраняет его имя, возраст, краткое био и локацию.
Локация сохраняется одним из двух образов: либо пользователь отправляет свою геолокацию через телеграм, либо
он присылает название своего города или другого места в формате "Страна, город, Область (по желанию, в случае если много городов с таким названием)
Если в списке локаций не выпадает та, которая нужна пользователю, то он может уточнить ее нажав кнопку "назад".
### Меню и профиль
![image](https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/9edf2343-048d-4a05-be33-616956d017c1)
На фото выше пользователь совершил следующие действия: Перешел в меню, перешел в профиль, нажал изменить локацию и выбрал подходящий город.
Разберем поподробнее: меню состоит из трех кнопок: Мои путешествия 🌴, Добавить путешествие 🛫 и Профиль 👫. 

Меню профиля дает возможность редактировать все те данные, которые пользователь вводил при регистрации.

### Создать путешествие
  ![image](https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/16a5eb5d-cc70-4005-9a4a-253b9eabcf59)
  при создании путешествия нужно указать его название, описание, количество локаций и сами локации.
  Для каждой локации указывается дата, когда нужно прибыть в нее и дата, когда из нее улетают.
  формат локации строгий, но это минимизирует риски неожиданных ошибок.
### Добавить друга
![image](https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/b3999398-f7ee-46f6-bf88-194dd314ee24)
  Добавить друга - это функция путешествия, она генерирует одноразовую ссылку, которую можно отправить уже зарегестрированному в боте другу
  и тот сможет присоединиться к путешествию. Всем участникам путешествия приходит оповещение.
### маршрут путешествия, изменить путешествие, удалить путешествие
![image](https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/bc8f0371-f5a9-4ade-81f6-525f6a5e0498)
  Маршрут строится от точки нахождения пользователя, который его запрашивает. Его местонахождение отмечено зеленой точкой. используется openstreetmaps.
  изменения путешествия простые: добавить локацию, изменить имя, изменить описание.
### локации
![image](https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/c99bf43a-1a1c-457d-b9a0-9272e698bdfa)
Идем по списку функций локации:
  1. Узнать о локации - функция на основе Yandex GPT, рассказывает от лица гида про ту локацию, на которую пользователь нажал.
  2. Узнать погоду - функция на основе Open Meteo API, может делать прогноз на __не более, чем 10 дней__.
  3. Где поесть - функция выводит рестораны и кафе, которые находятся около локации. Используется бесплатный API FourSquare.
  4. Отели рядом - функция выводит отели, которые находятся около локации. Используется бесплатный API FourSquare.
  5. Билет на самолет - функция отображает билеты на самолет из города пользователя до локации, если они есть. Используется KupiBilet
  6. Билет на поезд - функция отображает билеты на поездка из города пользователя до локации, если они есть. Используется API Российских Железных Дорог.
     __Функция работает только если сервер, где запущен бот, находится в России__.
  7. Удалить локацию - понятно.
### Заметки
![image](https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/ff79a17c-5717-48e3-8172-cf0f0c38bf28)
В заметки пользователи могут добавлять файлы, фото и видео и делиться ими с другими участниками путешествия или сохранять для себя.

## Описание внешних интеграций
__YandexGPT__: использован, так как выполняет тот уровень задач, который требуется, а именно: 
рассказывает про локации, предлагает интересные места на локации и может дать полезную информацию про них.
Из аналогов, которые я находил, многие либо не работали на территории РФ, либо часто выдавали неверную информацию.

__PostgreSQL__: одна из лучших СУБД для средних и крупных проектов, вместе с драйвером asyncpg позволяет минимизировать временные затраты.

__FourSquareAPI__: я выбрал это api для кафе, ресторанов и отелей т.к. он исправно работает по всему миру, дает полную информацию о заведении
и к тому же полностью бесплатный.

__KupiBilet__: это был единственный бесплатный вариант сервиса, дающего возможность строить авиамаршруты с помощью api

__RZHD__: единственный бесплатный работающий api, дающий полную информацию с ценами, который мне удалось найти

__Open Meteo API__: полностью бесплатный и имеет гибкие настройки.

__Open Street Maps__: бесплатный и с полной настройкой всех деталей, с возможностью изменить цвета и тд.

## Схема данных СУБД

<img width="1102" alt="Снимок экрана 2024-03-26 в 05 13 27" src="https://github.com/Central-University-IT-prod/backend-XP-T/assets/91194815/0429dcdf-a8c5-4308-afae-81297d6bc12c">




