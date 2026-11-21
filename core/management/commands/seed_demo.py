from django.core.management.base import BaseCommand

from core.models import FAQ, Company, Experience, Post, Project, Service, SiteSettings, Stat, Testimonial


class Command(BaseCommand):
    help = "Dizaynni ko'rish uchun namunaviy ma'lumotlar qo'shadi (keyin admin paneldan o'zgartirasiz)."

    def handle(self, *args, **options):
        site = SiteSettings.load()
        if site.full_name == "Ism Familiya":
            site.headline = "Dasturchi va tadbirkor"
            site.hero_badge = "Yangi loyihalar uchun ochiqman"
            site.short_bio = "Bizneslar uchun zamonaviy veb-saytlar va avtomatlashtirish tizimlarini yarataman."
            site.about = (
                "Salom! Men 6 yildan beri veb-dasturlash bilan shug'ullanaman.\n\n"
                "Bu matnni admin paneldagi «Sayt sozlamalari» bo'limidan o'zgartirasiz."
            )
            site.location = "Toshkent, O'zbekiston"
            site.email = "info@example.com"
            site.save()

        if not Stat.objects.exists():
            for i, (v, l) in enumerate([("6+", "yillik tajriba"), ("40+", "bajarilgan loyiha"), ("15", "hamkor kompaniya")]):
                Stat.objects.create(value=v, label=l, order=i)
        if not site.hero_title:
            site.hero_title = "Bizneslar uchun raqamli tizimlar quraman"
            site.save()
        if not Service.objects.exists():
            for i, (t, d) in enumerate([
                ("Veb-dasturlash", "Tez va ishonchli saytlar, admin panellar va integratsiyalar."),
                ("Telegram botlar", "Savdo, buyurtma va mijozlar bilan ishlashni avtomatlashtiruvchi botlar."),
                ("Konsalting", "Raqamli o'sish strategiyasi va jarayonlarni tartibga solish bo'yicha maslahatlar."),
                ("Jamoa va mahsulot", "Texnik jamoani yig'ish, mahsulotni rejalashtirish va ishga tushirish."),
            ]):
                Service.objects.create(title=t, description=d, order=i)
        if not FAQ.objects.exists():
            FAQ.objects.create(question="Qanday loyihalar bilan ishlaysiz?", order=0,
                               answer="Veb-saytlar, ichki tizimlar va Telegram botlar. Batafsil — yozing.")
            FAQ.objects.create(question="Loyiha qancha vaqt oladi?", order=1,
                               answer="Odatda 2–8 hafta, hajmiga qarab.")
        if not Experience.objects.exists():
            Experience.objects.create(role="Texnik direktor", company="Namuna MChJ", period="2022 — hozir",
                                      description="Jamoani boshqarish va mahsulot arxitekturasi.", order=0)
            Experience.objects.create(role="Dasturchi", company="Misol Group", period="2019 — 2022",
                                      description="Veb-ilovalar va integratsiyalar.", order=1)
        if not Company.objects.exists():
            for i, name in enumerate(["Alfa", "Beta Group", "Gamma Tech", "Delta", "Omega"]):
                Company.objects.create(name=name, order=i)
        if not Project.objects.exists():
            Project.objects.create(title="Onlayn do'kon", summary="E-commerce platforma va admin panel",
                                   client="Alfa", year="2025", tags="Django, Dizayn")
            Project.objects.create(title="CRM tizimi", summary="Savdo bo'limi uchun ichki tizim",
                                   client="Beta Group", year="2024", tags="Python, Telegram bot")
        if not Testimonial.objects.exists():
            Testimonial.objects.create(author="Aziz Karimov", position="Alfa, direktor",
                                       text="Ish sifatli va o'z vaqtida topshirildi. Tavsiya qilaman!")
        if not Post.objects.exists():
            Post.objects.create(title="Blogimga xush kelibsiz!", send_to_telegram=False,
                                content="Bu birinchi namunaviy post. Admin paneldan yangi post qo'shing — "
                                        "u saytda va Telegram kanalingizda bir vaqtda chiqadi.")
        self.stdout.write(self.style.SUCCESS("Namunaviy ma'lumotlar qo'shildi."))
