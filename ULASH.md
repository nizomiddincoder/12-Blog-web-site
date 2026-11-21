# Ishga tushirish va ulash — bosqichma-bosqich

Tartib muhim: **avval sayt Railway'da ishlashi kerak**, chunki LinkedIn va Instagram saytingiz manziliga
qaytadi, Instagram esa rasm/videoni saytingizdan o'zi yuklab oladi.

Quyida `SAYT` deb yozilgan joyga o'z manzilingizni qo'yasiz, masalan `https://mysite.up.railway.app`.

---

## 1-bosqich. Kodni GitHub'ga yuklash

Railway kodni GitHub'dan oladi.

1. github.com → **New repository** → nom bering (masalan `blog-sayt`) → **Private** → Create.
2. Kompyuteringizda, loyiha papkasida:
   ```powershell
   git remote add origin https://github.com/<login>/blog-sayt.git
   git push -u origin main
   ```

> `.env`, `db.sqlite3` va `media/` GitHub'ga yuklanmaydi (`.gitignore`da) — bu to'g'ri.

---

## 2-bosqich. Railway

1. railway.com → **New Project** → **Deploy from GitHub repo** → `blog-sayt` ni tanlang.
2. Xizmat (service) ustiga bosing → **Settings → Networking → Generate Domain**.
   Chiqqan manzil — sizning `SAYT`ingiz.
3. **Volume qo'shish** (baza va yuklangan rasm/videolar shu yerda saqlanadi, aks holda har deployda o'chib ketadi):
   loyiha oynasida xizmat ustida o'ng tugma → **Attach Volume** → Mount path: `/data`.
4. Xizmat → **Variables** → quyidagilarni qo'shing:

   | Nomi | Qiymati |
   |---|---|
   | `SECRET_KEY` | uzun tasodifiy satr (pastdagi buyruq bilan yarating) |
   | `DATA_DIR` | `/data` |
   | `ADMIN_URL` | masalan `boshqaruv-7x2/` (admin panel manzili, o'zingiz o'ylab toping) |
   | `DJANGO_SUPERUSER_USERNAME` | admin login |
   | `DJANGO_SUPERUSER_EMAIL` | emailingiz |
   | `DJANGO_SUPERUSER_PASSWORD` | kuchli parol |
   | `TELEGRAM_BOT_TOKEN` | 3-bosqichdan |
   | `TELEGRAM_CHANNEL_ID` | 3-bosqichdan |

   `SECRET_KEY` yaratish:
   ```powershell
   .\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
5. Railway avtomatik qayta deploy qiladi. **Deployments** bo'limida yashil "Active" chiqishini kuting.
6. Tekshiring: `SAYT` — sayt ochiladi; `SAYT/boshqaruv-7x2/` — admin panel, yuqoridagi login/parol bilan kirasiz.
7. Admin panelda **Sayt sozlamalari**ni to'ldiring: ism, sarlavha, rasm, video, "Men haqimda" va h.k.

**O'z domeningiz bo'lsa** (ixtiyoriy): Settings → Networking → **Custom Domain** → ko'rsatilgan DNS yozuvini
domeningizga qo'shing. So'ng Variables'ga qo'shing: `SITE_URL=https://domeningiz.uz`,
`ALLOWED_HOSTS=domeningiz.uz`, `CSRF_TRUSTED_ORIGINS=https://domeningiz.uz`. Domen o'zgarsa, LinkedIn va
Instagram ilovalaridagi redirect manzilini ham yangilang.

---

## 3-bosqich. Telegram kanal

1. Telegramda **@BotFather** → `/newbot` → nom bering → **token** chiqadi.
2. Kanalingiz → Boshqaruv → Administratorlar → botni qo'shing. "Xabar joylash" va "Xabarlarni o'chirish"
   huquqlarini yoqing.
3. Railway Variables: `TELEGRAM_BOT_TOKEN=<token>`, `TELEGRAM_CHANNEL_ID=@kanal_nomi`.
   Yopiq kanal bo'lsa, ID `-100…` ko'rinishida bo'ladi.

---

## 4-bosqich. LinkedIn (shaxsiy profil)

1. https://www.linkedin.com/developers/apps → **Create app**.
   - App name: masalan "Mening blogim".
   - **LinkedIn Page**: LinkedIn ilova yaratish uchun kompaniya sahifasini so'raydi. Sizda sahifa bo'lmasa,
     LinkedIn'da bepul sahifa oching (masalan, ismingiz bilan). Postlar baribir **shaxsiy profilingizga**
     chiqadi, sahifa faqat ilovani ro'yxatdan o'tkazish uchun kerak.
   - Privacy policy URL: `SAYT/maxfiylik/`
   - Logo yuklang → **Create app**.
2. **Products** yorlig'i → ikkalasiga **Request access** bosing (ruxsat darhol beriladi):
   - *Share on LinkedIn*
   - *Sign In with LinkedIn using OpenID Connect*
3. **Auth** yorlig'i:
   - **Authorized redirect URLs** → qo'shing: `SAYT/connect/linkedin/callback/`
     (aniq manzil admin paneldagi **Ijtimoiy tarmoqlarni ulash** sahifasida ham yozilgan).
   - **Client ID** va **Primary Client Secret** ni nusxalang.
4. Railway Variables: `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`.
5. Admin panel → **Ijtimoiy tarmoqlarni ulash** → LinkedIn → **Ulash** → LinkedIn'da **Allow**.
   "✓ Tayyor" chiqadi.

> Ulanish **60 kun** amal qiladi. Muddati shu sahifada ko'rinadi. Tugashiga yaqin **Qayta ulash** tugmasini
> bosasiz (10 soniyalik ish).

---

## 5-bosqich. Instagram (Business akkaunt)

1. https://developers.facebook.com → **My Apps → Create App**.
   - Use case: **Manage messaging & content on Instagram** → Next.
   - Nom va email kiriting → Create. Biznes portfoli so'ralsa, o'tkazib yuborish mumkin.
2. Ilova panelida: **Instagram → API setup with Instagram business login**.
   - **Instagram app ID** va **Instagram app secret** ni nusxalang. Bular Meta App ID'dan farq qiladi!
   - **Set up Instagram business login → Business login settings** → **OAuth redirect URIs** ga
     `SAYT/connect/instagram/callback/` ni qo'shing → Save.
3. **App roles → Roles → Add People → Instagram Tester** → Instagram username'ingizni kiriting.
   Keyin Instagram'da: **Sozlamalar → Ilovalar va veb-saytlar → Tester takliflari → Qabul qilish**.
   Bu sozlama Instagram veb-versiyasida joylashgan bo'lishi mumkin.
4. **App settings → Basic**: Privacy Policy URL va User data deletion URL ga `SAYT/maxfiylik/` yozing → Save.
5. Railway Variables: `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`.
6. Admin panel → **Ijtimoiy tarmoqlarni ulash** → Instagram → **Ulash** → Instagram'da ruxsat bering.

> Ilova "Development" rejimida qoladi — o'z akkauntingizga post joylash uchun Meta tekshiruvi (App Review)
> **kerak emas**. Instagram ulanishi ham 60 kunlik, lekin sayt uni o'zi avtomatik yangilab turadi.

---

## 6-bosqich. Foydalanish

Admin → **Postlar → Qo'shish**:
1. Sarlavha, matn yozasiz, rasm/videolarni tanlaysiz (bir nechtasini birdan).
2. "E'lon qilish" bo'limida qaysi platformalarga ketishini belgilaysiz: ☑ Telegram ☑ LinkedIn ☑ Instagram.
3. **Saqlash** → post saytda chiqadi va belgilangan platformalarga fon rejimida yuboriladi.
4. Post sahifasining pastida **Platformalardagi holat** jadvali bor: har biri uchun "Yuborildi" va havola
   yoki xato matni.

| Post turi | Telegram | LinkedIn | Instagram |
|---|---|---|---|
| Faqat matn | ✓ | ✓ | — (Instagram qabul qilmaydi) |
| 1 rasm | ✓ | ✓ | ✓ post |
| Bir nechta rasm | ✓ albom | ✓ 20 tagacha | ✓ karusel, 10 tagacha |
| 1 video | ✓ | ✓ | ✓ Reels |
| Rasm + video aralash | ✓ | faqat video | ✓ karusel |

**Sifat:** sayt va Telegram (fayl rejimida) asl faylni saqlaydi. LinkedIn va Instagram har qanday faylni o'z
serverida qayta siqadi, buni chetlab o'tib bo'lmaydi. Biz ularga asl faylni yuboramiz.
Instagram faqat JPEG va 4:5 dan 1.91:1 gacha nisbatni qabul qiladi. Mos kelmagan rasm uchun sayt
**faqat Instagram uchun** JPEG nusxa yasaydi (kerak bo'lsa oq hoshiya bilan). Saytdagi asl fayl o'zgarmaydi.

**Tahrirlash:** postni tahrirlasangiz, u qayta yuborilmaydi. Ro'yxatda postni belgilab, **Amal** orqali:
- *Yangilash* — Telegram va LinkedIn'da eski post o'chib, yangisi joylanadi. Instagram API post
  o'chirishga ruxsat bermaydi, u yerda qo'lda tahrirlaysiz.
- *O'chirish* — Telegram va LinkedIn'dan o'chiradi, saytda qoladi.
- *Yuborilmagan/xato bo'lganlarga yuborish* — masalan, LinkedIn'ni keyinroq ulagan bo'lsangiz.

**Rejalashtirish:** "E'lon vaqti"ga kelajakdagi vaqtni qo'ysangiz, o'sha vaqtda hamma joyda chiqadi.
Buni Railway'da avtomatik ishlaydigan fon jarayoni bajaradi.

---

## Muammo bo'lsa

- **"Ulanmagan / kalitlar yo'q"** — Railway Variables'ni tekshiring, saqlagandan keyin deploy tugashini kuting.
- **LinkedIn: `redirect_uri does not match`** — ilovadagi redirect URL admin sahifadagi bilan harfma-harf
  bir xil bo'lishi kerak (oxiridagi `/` ham).
- **LinkedIn: `NONEXISTENT_VERSION` yoki `426`** — Variables'ga `LINKEDIN_API_VERSION` ni yangiroq oyga
  qo'ying (masalan `202610`).
- **Instagram: `Insufficient developer role`** — 5-bosqichning 3-bandi (Tester taklifini qabul qilish).
- **Instagram: rasm/video yuklanmadi** — sayt internetdan ochilishini tekshiring. Video MP4 (H.264) bo'lsin.
- **Railway: har deploydan keyin postlar yo'qoladi** — Volume `/data` ga ulanmagan yoki `DATA_DIR` yo'q.

Keyingi bosqich: **YouTube va TikTok** (ular auditdan o'tishni talab qiladi).
