# Shaxsiy blog-sayt + Telegram, LinkedIn, Instagram

Admin paneldan post qo'shasiz → post **saytda**, **Telegram kanalda**, **LinkedIn profilingizda** va
**Instagram**da bir vaqtda chiqadi. Sayt sizni tanishtiradi: kimsiz, nima qilasiz, qilgan ishlaringiz,
siz bilan ishlagan kompaniyalar, tajriba, fikrlar, savol-javoblar. Hammasi admin paneldan o'zgartiriladi.

**Ishga tushirish va ulash bo'yicha to'liq qo'llanma: [ULASH.md](ULASH.md)** (Railway, Telegram, LinkedIn, Instagram).

**Texnologiya:** Python 3.12 · Django 6 · SQLite · Railway · Telegram Bot API · LinkedIn Posts API ·
Instagram API (Instagram Login)

Kod tuzilishi: `core/publishers/` — har bir platforma alohida modul (yangi platforma qo'shish oson),
`core/publishing.py` — navbat va holatlar, `core/connect_views.py` — akkauntlarni ulash.

## Rasm va video sifati

- Yuklangan fayllar **hech qachon siqilmaydi va qayta kodlanmaydi** — diskda baytma-bayt asl holida
  saqlanadi va saytda aynan shu asl fayl ko'rsatiladi.
- **Telegram:** videolar `sendVideo` orqali yuboriladi, Telegram ularni qayta kodlamaydi.
  Rasmlar esa Telegramga "rasm" sifatida yuborilsa, Telegram ularni **doim** siqadi (bu Telegramning
  o'z qoidasi). Shuning uchun *Sayt sozlamalari → Telegramga rasm yuborish usuli*:
  - **Asl sifatda** (standart) — rasm fayl ko'rinishida yuboriladi, sifat 100% saqlanadi;
  - **Oddiy rasm** — kanalda chiroyli albom bo'lib chiqadi, lekin Telegram biroz siqadi.
- Rasmiy Bot API bot uchun **50 MB** fayl limitini qo'yadi. Undan katta video saytda chiqadi,
  Telegram postida esa "Batafsil o'qish" havolasi bo'ladi. Limitni 2 GB gacha oshirish uchun
  o'zingizning [Bot API serveringiz](https://github.com/tdlib/telegram-bot-api)ni ishga tushirib,
  `.env` da `TELEGRAM_API_BASE` va `TELEGRAM_MAX_UPLOAD_MB` ni o'zgartirasiz.

## Kompyuterda ishga tushirish (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py createsuperuser
.\.venv\Scripts\python manage.py runserver
```

- Sayt: http://localhost:8000
- Admin panel: http://localhost:8000/admin/
- Namunaviy ma'lumot bilan dizaynni ko'rish: `python manage.py seed_demo`

## Telegram kanalni ulash

1. Telegramda **@BotFather** → `/newbot` → bot yarating va **token**ni oling.
2. Botni kanalingizga **administrator** qilib qo'shing ("Xabar joylash" va "Xabarlarni o'chirish" huquqlari bilan).
3. `.env` faylida:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHANNEL_ID=@kanalingiz_nomi
   SITE_URL=https://saytingiz.uz
   ```
   Yopiq kanal bo'lsa `TELEGRAM_CHANNEL_ID=-100...` ko'rinishidagi ID yoziladi.
4. Tekshirish: `python manage.py telegram_check`

## Admin panelda nima bor

| Bo'lim | Nima uchun |
|---|---|
| **Sayt sozlamalari** | Ism, kasb, qisqa tanishtiruv, rasm, "Men haqimda", aloqa, ijtimoiy tarmoqlar, asosiy rang, Telegram rejimi |
| **Postlar (yangiliklar)** | Sarlavha, matn, bir nechta rasm/video (bir vaqtda tanlab yuklash mumkin) |
| **Loyihalar (qilgan ishlarim)** | Muqova, tavsif, mijoz, yil, teglar, galereya |
| **Men bilan ishlagan kompaniyalar** | Logotip, nom, sayt havolasi |
| **Tajriba**, **Xizmatlar**, **Raqamlar**, **Fikr-mulohazalar** | Bosh sahifadagi bo'limlar |

Har bir ro'yxatda **Tartib** raqami bor — kichik raqam oldinda chiqadi. Bo'lim bo'sh bo'lsa saytda ko'rinmaydi.

### Post va Telegram

- Post saqlanganda "Saytda e'lon qilish" va "Telegram kanalga ham yuborish" belgilangan bo'lsa,
  post fon rejimida kanalga yuboriladi. Holati ro'yxatdagi **Telegram** ustunida ko'rinadi
  (Yuborildi / Xatolik — xato matni postning ichida yoziladi).
- Ro'yxatdan postlarni belgilab, **Amallar** orqali:
  - *Telegramga yuborish* — yuborilmagan yoki xato bo'lganlarni qayta yuborish;
  - *Telegramda yangilash* — postni tahrirlaganingizdan so'ng: eski xabar o'chadi, yangisi joylanadi;
  - *Telegram kanaldan o'chirish* — saytda qoladi, kanaldan o'chadi.
- Matn 1024 belgidan qisqa bo'lsa — rasm/video ostiga izoh bo'lib chiqadi; uzun bo'lsa — avval
  media, keyin to'liq matn alohida xabar bo'lib chiqadi.

### Rejalashtirilgan postlar

"E'lon vaqti"ga kelajakdagi vaqt qo'ysangiz, post o'sha vaqtda saytda paydo bo'ladi. Telegramga ham
o'sha vaqtda chiqishi uchun serverda quyidagi buyruq doim ishlab tursin (yoki cron orqali har daqiqada):

```
python manage.py publish_scheduled --loop
```

## Serverga joylash (qisqacha)

1. `.env`: `DEBUG=False`, uzun `SECRET_KEY`, `ALLOWED_HOSTS=saytingiz.uz`,
   `CSRF_TRUSTED_ORIGINS=https://saytingiz.uz`, `SITE_URL=https://saytingiz.uz`, `ADMIN_URL` ni o'zgartiring.
2. `python manage.py migrate` va `python manage.py collectstatic`
3. `gunicorn config.wsgi:application --workers 2 --threads 4 --timeout 600`
4. nginx: `/media/` papkasini to'g'ridan-to'g'ri bersin va katta video yuklash uchun limitni oshiring:
   ```nginx
   client_max_body_size 2G;
   location /media/ { alias /yo'l/loyiha/media/; }
   location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host;
                proxy_set_header X-Forwarded-Proto $scheme; proxy_read_timeout 600; }
   ```
5. `media/` papkasi va `db.sqlite3` faylini muntazam zaxiralang.

## Dizayn

Ranglar, shrift, burchak radiuslari `static/css/style.css` boshidagi tokenlarda.
Referens dizayn asosida shablonlar (`templates/`) va shu CSS moslashtiriladi.

## Testlar

```
python manage.py test core
```
