# Календарь матчей ЦСКА

Раз в день собирает матчи ПФК ЦСКА, ХК ЦСКА и ПБК ЦСКА: страница-календарь, сводка в Telegram и файл `web/calendar.ics`.

## Запуск

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m cska
.venv/bin/python -m cska serve
```

Календарь открывается на [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Публичная копия: [serganizm.github.io/cska](https://serganizm.github.io/cska/). Её обновляет GitHub Actions каждый день в 09:00 по Москве и при каждом пуше в `main`.

В `.env` нужны `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`. Без них сбор всё равно обновляет страницу и `.ics`, а сообщения не отправляет. Chat id можно взять у [@userinfobot](https://t.me/userinfobot) или из `getUpdates` после сообщения своему боту.

Таймер пользователя ставится так:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/cska-calendar.service deploy/cska-calendar.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now cska-calendar.timer
```

Сбор идёт каждый день в 09:00 по местному времени. Чтобы таймер работал без открытой сессии: `loginctl enable-linger "$USER"`.

Матч без назначенного часа остаётся на сайте и в Telegram строкой вроде «9–12 октября, время не назначено» и не попадает в `.ics`, пока не появятся день и час.
