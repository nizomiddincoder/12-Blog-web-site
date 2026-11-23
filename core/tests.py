import io
import json
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core import publishing
from core.models import Post, PostDelivery, PostMedia, SiteSettings, SocialAccount
from core.publishers import instagram, linkedin
from core.publishers import telegram as tg

TMP_MEDIA = tempfile.mkdtemp()
Status = PostDelivery.Status


def jpeg_bytes(size=(1600, 900), fmt="JPEG"):
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buf, fmt, quality=98)
    return buf.getvalue()


class FakeResponse:
    def __init__(self, result=None, status=200, headers=None, payload=None):
        self.status_code = status
        self.headers = headers or {}
        self._payload = payload if payload is not None else {"ok": True, "result": result}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeTelegram:
    def __init__(self):
        self.calls = []

    def __call__(self, url, data=None, files=None, timeout=None):
        method = url.rsplit("/", 1)[1]
        self.calls.append((method, data, files))
        if method == "sendMediaGroup":
            return FakeResponse([{"message_id": i} for i in range(len(json.loads(data["media"])))])
        return FakeResponse({"message_id": 1} if method != "deleteMessages" else True)


class SyncThread:
    """Testda fon oqimi o'rniga darhol bajaradi."""

    def __init__(self, target, args, daemon=None):
        self.target, self.args = target, args

    def start(self):
        items, repost = self.args
        for post_id, platform in items:
            publishing.run(post_id, platform, repost=repost)


TG = dict(TELEGRAM_BOT_TOKEN="1:T", TELEGRAM_CHANNEL_ID="@kanal")
NO_SOCIAL = dict(LINKEDIN_CLIENT_ID="", LINKEDIN_CLIENT_SECRET="", INSTAGRAM_APP_ID="", INSTAGRAM_APP_SECRET="")


@override_settings(MEDIA_ROOT=TMP_MEDIA, SITE_URL="https://misol.uz", **TG, **NO_SOCIAL)
class AdminFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("boss", "b@example.com", "x-pass-123")
        self.client.force_login(self.admin)

    def add_post(self, **extra):
        data = {
            "title": "Admin orqali post", "content": "Matn", "is_published": "on",
            "published_at_0": "2020-01-01", "published_at_1": "10:00:00",
            "send_to_telegram": "on", "send_to_linkedin": "on", "send_to_instagram": "on", "slug": "",
            "media-TOTAL_FORMS": "0", "media-INITIAL_FORMS": "0",
            "media-MIN_NUM_FORMS": "0", "media-MAX_NUM_FORMS": "1000",
            "deliveries-TOTAL_FORMS": "0", "deliveries-INITIAL_FORMS": "0",
            "deliveries-MIN_NUM_FORMS": "0", "deliveries-MAX_NUM_FORMS": "1000",
        }
        data.update(extra)
        return self.client.post(reverse("admin:core_post_add"), data)

    def send(self, fake, **extra):
        with mock.patch("core.publishers.telegram.requests.post", side_effect=fake), \
                mock.patch("core.publishing.threading.Thread", SyncThread), \
                self.captureOnCommitCallbacks(execute=True):
            return self.add_post(**extra)

    def test_upload_keeps_original_bytes_and_sends_only_to_ready_platforms(self):
        raw = jpeg_bytes()
        fake = FakeTelegram()
        response = self.send(fake, new_media=[SimpleUploadedFile("a.jpg", raw), SimpleUploadedFile("b.jpg", raw)])
        self.assertEqual(response.status_code, 302)

        post = Post.objects.get()
        media = list(post.media.all())
        with media[0].file.open("rb") as fh:
            self.assertEqual(fh.read(), raw)  # bayt-ma-bayt bir xil
        self.assertEqual((media[0].width, media[0].height), (1600, 900))

        deliveries = {d.platform: d for d in post.deliveries.all()}
        self.assertEqual(set(deliveries), {"telegram"})  # LinkedIn/Instagram ulanmagan
        self.assertEqual(deliveries["telegram"].status, Status.SENT)
        self.assertEqual(deliveries["telegram"].external_url, "https://t.me/kanal/0")
        sent = json.loads(fake.calls[0][1]["media"])
        self.assertEqual([m["type"] for m in sent], ["document", "document"])
        self.assertIn("https://misol.uz/blog/", sent[0]["caption"])

    def test_editing_does_not_resend(self):
        fake = FakeTelegram()
        self.send(fake)
        post = Post.objects.get()
        fake.calls.clear()
        with mock.patch("core.publishers.telegram.requests.post", side_effect=fake), \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("admin:core_post_change", args=[post.pk]), {
                "title": "Yangi sarlavha", "content": "x", "is_published": "on",
                "published_at_0": "2020-01-01", "published_at_1": "10:00:00", "send_to_telegram": "on",
                "slug": post.slug, "media-TOTAL_FORMS": "0", "media-INITIAL_FORMS": "0",
                "deliveries-TOTAL_FORMS": "0", "deliveries-INITIAL_FORMS": "0",
            })
        self.assertEqual(fake.calls, [])

    def test_compressed_mode_uses_photos(self):
        SiteSettings.objects.update_or_create(pk=1, defaults={"telegram_media_mode": "compressed"})
        fake = FakeTelegram()
        self.send(fake, new_media=[SimpleUploadedFile("a.jpg", jpeg_bytes())])
        self.assertEqual(fake.calls[0][0], "sendPhoto")

    def test_future_post_is_scheduled_then_sent(self):
        fake = FakeTelegram()
        future = timezone.localtime() + timedelta(days=1)
        self.send(fake, published_at_0=future.strftime("%Y-%m-%d"), published_at_1=future.strftime("%H:%M:%S"))
        delivery = PostDelivery.objects.get()
        self.assertEqual(delivery.status, Status.SCHEDULED)
        self.assertEqual(fake.calls, [])
        Post.objects.update(published_at=timezone.now() - timedelta(minutes=1))
        with mock.patch("core.publishers.telegram.requests.post", side_effect=fake):
            publishing.run_scheduled()
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, Status.SENT)

    def test_unpublished_post_is_not_sent(self):
        fake = FakeTelegram()
        self.send(fake, is_published="")
        self.assertEqual(fake.calls, [])
        self.assertFalse(PostDelivery.objects.exists())

    def test_rejects_unknown_file_type(self):
        response = self.add_post(new_media=[SimpleUploadedFile("x.exe", b"MZ")])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.exists())

    def test_failure_is_recorded(self):
        def boom(*a, **k):
            return FakeResponse(status=400, payload={"ok": False, "description": "Bad Request: chat not found"})

        self.send(boom)
        delivery = PostDelivery.objects.get()
        self.assertEqual(delivery.status, Status.FAILED)
        self.assertIn("chat not found", delivery.message)

    def test_connections_page(self):
        response = self.client.get(reverse("admin:core_socialaccount_changelist"))
        self.assertContains(response, "LinkedIn")
        self.assertContains(response, "/connect/instagram/callback/")


class FakeHTTP:
    """requests.request o'rnini bosuvchi: (method, url-qismi) bo'yicha javob qaytaradi."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        for (m, part), resp in self.routes.items():
            if m == method and part in url:
                return resp(kwargs) if callable(resp) else resp
        raise AssertionError(f"Kutilmagan so'rov: {method} {url}")


@override_settings(
    MEDIA_ROOT=TMP_MEDIA, SITE_URL="https://misol.uz",
    LINKEDIN_CLIENT_ID="li", LINKEDIN_CLIENT_SECRET="sec", LINKEDIN_API_VERSION="202607",
    INSTAGRAM_APP_ID="ig", INSTAGRAM_APP_SECRET="sec2", INSTAGRAM_API_VERSION="v25.0",
)
class SocialPublisherTests(TestCase):
    def make_post(self, files=()):
        post = Post.objects.create(title="Sarlavha (test) #yangilik", content="Matn_1 *muhim*")
        for i, (name, data) in enumerate(files):
            PostMedia.objects.create(post=post, file=SimpleUploadedFile(name, data), order=i)
        return post

    def test_linkedin_multi_image_post(self):
        SocialAccount.objects.create(platform="linkedin", account_id="abc", access_token="TOK",
                                     expires_at=timezone.now() + timedelta(days=50))
        post = self.make_post([("a.jpg", jpeg_bytes()), ("b.png", jpeg_bytes(fmt="PNG"))])
        counter = iter(range(10))
        fake = FakeHTTP({
            ("POST", "/rest/images?action=initializeUpload"): lambda kw: FakeResponse(payload={"value": {
                "uploadUrl": "https://upload.example/x", "image": f"urn:li:image:{next(counter)}"}}),
            ("PUT", "upload.example"): FakeResponse(payload={}),
            ("POST", "/rest/posts"): FakeResponse(status=201, payload={}, headers={"x-restli-id": "urn:li:share:9"}),
        })
        with mock.patch("core.publishers.base.requests.request", side_effect=fake):
            result = linkedin.LinkedInPublisher().publish(post)
        body = fake.calls[-1][2]["json"]
        self.assertEqual(body["author"], "urn:li:person:abc")
        self.assertEqual(len(body["content"]["multiImage"]["images"]), 2)
        self.assertIn("Sarlavha \\(test\\) {hashtag|\\#|yangilik}", body["commentary"])
        self.assertIn("Matn\\_1 \\*muhim\\*", body["commentary"])
        self.assertEqual(fake.calls[-1][2]["headers"]["LinkedIn-Version"], "202607")
        self.assertEqual(result.url, "https://www.linkedin.com/feed/update/urn:li:share:9/")

    def test_linkedin_expired_token(self):
        SocialAccount.objects.create(platform="linkedin", account_id="abc", access_token="T",
                                     expires_at=timezone.now() - timedelta(days=1))
        self.assertIn("muddati", linkedin.LinkedInPublisher().problem())

    def test_instagram_carousel_and_jpeg_copy(self):
        SocialAccount.objects.create(platform="instagram", account_id="17841", access_token="IGT",
                                     expires_at=timezone.now() + timedelta(days=50))
        # PNG va juda tik rasm -> Instagram uchun JPEG nusxa yasaladi; asl fayl o'zgarmaydi
        png = jpeg_bytes((600, 2000), "PNG")
        post = self.make_post([("tik.png", png), ("b.jpg", jpeg_bytes())])
        ids = iter(range(100, 200))
        fake = FakeHTTP({
            ("POST", "/17841/media_publish"): FakeResponse(payload={"id": "999"}),
            ("POST", "/17841/media"): lambda kw: FakeResponse(payload={"id": str(next(ids))}),
            ("GET", "/999"): FakeResponse(payload={"permalink": "https://instagram.com/p/x"}),
            ("GET", "graph.instagram.com/v25.0/1"): FakeResponse(payload={"status_code": "FINISHED"}),
        })
        with mock.patch("core.publishers.base.requests.request", side_effect=fake):
            result = instagram.InstagramPublisher().publish(post)
        creates = [c[2]["data"] for c in fake.calls if c[0] == "POST" and c[1].endswith("/media")]
        self.assertTrue(creates[0]["image_url"].startswith("https://misol.uz/media/instagram/"))
        self.assertTrue(creates[1]["image_url"].endswith("b.jpg"))
        self.assertEqual(creates[2]["media_type"], "CAROUSEL")
        self.assertEqual(result.url, "https://instagram.com/p/x")
        with post.media.first().file.open("rb") as fh:
            self.assertEqual(fh.read(), png)
        copy = post.media.first().file.storage.open(creates[0]["image_url"].split("/media/")[1])
        with Image.open(copy) as img:
            self.assertAlmostEqual(img.width / img.height, 0.8, places=2)

    @override_settings(MAKE_INSTAGRAM_WEBHOOK_URL="https://hook.eu2.make.com/abc", INSTAGRAM_APP_ID="")
    def test_instagram_via_make_webhook(self):
        publisher = instagram.InstagramPublisher()
        self.assertTrue(publisher.is_ready())  # akkaunt ulamasdan ham tayyor
        self.assertFalse(publisher.uses_oauth)
        post = self.make_post([("a.jpg", jpeg_bytes()), ("b.jpg", jpeg_bytes())])
        fake = FakeHTTP({("POST", "hook.eu2.make.com"): FakeResponse(payload={})})
        with mock.patch("core.publishers.base.requests.request", side_effect=fake):
            result = publisher.publish(post)
        payload = fake.calls[0][2]["json"]
        self.assertEqual(payload["type"], "carousel")
        self.assertFalse(payload["test"])
        self.assertEqual([m["media_type"] for m in payload["media"]], ["IMAGE", "IMAGE"])
        self.assertTrue(payload["image_url"].startswith("https://misol.uz/media/posts/"))
        self.assertIn("Sarlavha", payload["caption"])
        self.assertIn("Make", result.warnings[-1])

        # bitta video -> reel
        video_post = Post.objects.create(title="Video")
        PostMedia.objects.create(post=video_post, file=SimpleUploadedFile("v.mp4", b"0000"))
        with mock.patch("core.publishers.base.requests.request", side_effect=fake):
            publisher.publish(video_post)
        self.assertEqual(fake.calls[-1][2]["json"]["type"], "reel")

        # namuna
        with mock.patch("core.publishers.base.requests.request", side_effect=fake):
            sample = publisher.send_sample()
        self.assertTrue(sample["test"])

    def test_instagram_skips_text_only(self):
        SocialAccount.objects.create(platform="instagram", account_id="1", access_token="T",
                                     expires_at=timezone.now() + timedelta(days=50))
        from core.publishers import Skip
        with self.assertRaises(Skip):
            instagram.InstagramPublisher().publish(self.make_post())

    @override_settings(SITE_URL="")
    def test_instagram_needs_public_site(self):
        SocialAccount.objects.create(platform="instagram", account_id="1", access_token="T")
        self.assertIn("internetda", instagram.InstagramPublisher().problem())


@override_settings(ANTHROPIC_API_KEY="sk-ant-test", COMPOSIO_API_KEY="cmp-test",
                   COMPOSIO_MCP_URL="https://connect.composio.dev/mcp")
class StatsSyncTests(TestCase):
    CLAUDE_TEXT = json.dumps({
        "instagram": {"followers": 1234, "media_count": 40,
                      "recent_posts": [{"likes": 10, "comments": 2}, {"likes": 30, "comments": 4}]},
        "youtube": None,
        "errors": [],
    })

    def fake_response(self, text):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"content": [{"type": "text", "text": text}]}
        return resp

    def test_sync_saves_metrics_and_sends_mcp_request(self):
        from core import stats_sync
        from core.stats_models import StatSnapshot

        with mock.patch("core.stats_sync.requests.post", return_value=self.fake_response(self.CLAUDE_TEXT)) as post:
            count = stats_sync.sync()
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["mcp_servers"][0]["url"], "https://connect.composio.dev/mcp")
        self.assertEqual(sent["mcp_servers"][0]["authorization_token"], "cmp-test")
        self.assertEqual(sent["tools"][0]["type"], "mcp_toolset")
        self.assertEqual(post.call_args.kwargs["headers"]["x-api-key"], "sk-ant-test")

        self.assertEqual(count, 4)  # followers, media_count, avg_likes, avg_comments
        values = dict(StatSnapshot.objects.values_list("metric", "value"))
        self.assertEqual(values["followers"], 1234)
        self.assertEqual(values["avg_likes_last5"], 20)
        self.assertEqual(values["avg_comments_last5"], 3)
        self.assertFalse(StatSnapshot.objects.filter(platform="youtube").exists())

    def test_text_around_json_is_tolerated(self):
        from core import stats_sync

        with mock.patch("core.stats_sync.requests.post",
                        return_value=self.fake_response("Mana natija:\n" + self.CLAUDE_TEXT + "\nRahmat")):
            self.assertEqual(stats_sync.sync(), 4)

    def test_bad_json_is_reported(self):
        from core import stats_sync

        with mock.patch("core.stats_sync.requests.post", return_value=self.fake_response("bu JSON emas")):
            with self.assertRaises(stats_sync.StatsError):
                stats_sync.sync()

    def test_api_error_is_reported_without_key(self):
        from core import stats_sync

        resp = mock.Mock(status_code=401, text="invalid x-api-key")
        with mock.patch("core.stats_sync.requests.post", return_value=resp):
            with self.assertRaises(stats_sync.StatsError) as ctx:
                stats_sync.sync()
        self.assertNotIn("sk-ant-test", str(ctx.exception))

    @override_settings(COMPOSIO_API_KEY="")
    def test_missing_key_is_clear(self):
        from core import stats_sync

        with self.assertRaisesMessage(stats_sync.StatsError, "COMPOSIO_API_KEY"):
            stats_sync.build_request()

    def test_sync_stats_command_skips_when_fresh(self):
        from django.core.management import call_command
        from io import StringIO
        from core.stats_models import StatSnapshot

        StatSnapshot.objects.create(platform="instagram", metric="followers", value=5)
        out = StringIO()
        with mock.patch("core.stats_sync.requests.post") as post:
            call_command("sync_stats", "--if-stale", stdout=out)
        post.assert_not_called()
        self.assertIn("o'tkazib", out.getvalue())


@override_settings(MAKE_RESULT_SECRET="s3cret-test")
class MakeResultTests(TestCase):
    def setUp(self):
        self.post = Post.objects.create(title="Reel test")
        self.delivery = PostDelivery.objects.create(post=self.post, platform="instagram",
                                                    status=PostDelivery.Status.QUEUED)

    def send(self, body, secret="s3cret-test"):
        headers = {"HTTP_X_MAKE_SECRET": secret} if secret is not None else {}
        return self.client.post("/api/make/result/", data=json.dumps(body),
                                content_type="application/json", **headers)

    def test_rejects_wrong_secret(self):
        self.assertEqual(self.send({"post_id": self.post.pk, "platform": "instagram", "external_id": "1"},
                                   secret="nope").status_code, 403)
        self.assertEqual(self.send({"post_id": self.post.pk, "platform": "instagram", "external_id": "1"},
                                   secret=None).status_code, 403)

    def test_saves_external_id_and_marks_sent(self):
        resp = self.send({"post_id": self.post.pk, "platform": "instagram", "external_id": "178900",
                          "url": "https://instagram.com/p/abc"})
        self.assertEqual(resp.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.external_ids, ["178900"])
        self.assertEqual(self.delivery.status, PostDelivery.Status.SENT)
        self.assertIsNotNone(self.delivery.sent_at)

    def test_unknown_delivery_is_404(self):
        resp = self.send({"post_id": self.post.pk, "platform": "youtube", "external_id": "x"})
        self.assertEqual(resp.status_code, 404)


class PostStatsRuleTests(TestCase):
    def make_sent(self, platform, days_ago, ext="ID1"):
        post = Post.objects.create(title=f"{platform} {days_ago}")
        return PostDelivery.objects.create(
            post=post, platform=platform, status=PostDelivery.Status.SENT,
            external_ids=[ext], sent_at=timezone.now() - timedelta(days=days_ago))

    def test_thirty_day_window_and_cadence(self):
        from core import post_stats
        from core.stats_models import PostStat as PS

        fresh = self.make_sent("instagram", 1)       # 1 kun: kuniga bir marta -> due
        old = self.make_sent("instagram", 31)        # 30 kundan keyin -> yo'q
        telegram = self.make_sent("telegram", 1)     # faqat IG/YT -> yo'q
        self.assertEqual([d.pk for d in post_stats.due_targets()], [fresh.pk])

        PS.objects.create(post=fresh.post, platform="instagram", external_id="ID1", metric="likes", value=1)
        self.assertEqual(post_stats.due_targets(), [])  # bugun allaqachon olingan

        week_old = self.make_sent("youtube", 10)     # 7 kundan keyin: haftada bir marta
        PS.objects.create(post=week_old.post, platform="youtube", external_id="ID1", metric="views", value=5)
        PS.objects.filter(post=week_old.post).update(fetched_at=timezone.now() - timedelta(days=2))
        self.assertEqual(post_stats.due_targets(), [])
        self.assertNotIn(old.pk, [d.pk for d in post_stats.due_targets()])
        self.assertNotIn(telegram.pk, [d.pk for d in post_stats.due_targets()])

    def test_parse_matches_only_requested_ids(self):
        from core import post_stats

        d = self.make_sent("instagram", 1, ext="IG-1")
        text = json.dumps({"items": [
            {"platform": "instagram", "external_id": "IG-1", "likes": 12, "comments": 3, "views": None},
            {"platform": "instagram", "external_id": "UNKNOWN", "likes": 99},
        ]})
        rows = post_stats.parse(text, [d])
        self.assertEqual(sorted((m, v) for _, m, v in rows), [("comments", 3.0), ("likes", 12.0)])


class TelegramSubscribersTests(TestCase):
    @override_settings(TELEGRAM_BOT_TOKEN="1:T", TELEGRAM_CHANNEL_ID="@kanal")
    def test_subscriber_count_saved(self):
        from core import stats_sync
        from core.stats_models import StatSnapshot

        with mock.patch("core.publishers.telegram.requests.post", return_value=FakeResponse(42)):
            self.assertEqual(stats_sync.sync_telegram(), 1)
        row = StatSnapshot.objects.get(platform="telegram")
        self.assertEqual((row.metric, row.value), ("subscribers", 42.0))


class TextTests(TestCase):
    def test_caption_is_truncated_to_limit(self):
        post = Post(title="Sarlavha", content="😀 so'z " * 500, slug="s")
        text, truncated = tg.build_text(post, tg.CAPTION_LIMIT, "https://misol.uz/blog/s/")
        self.assertTrue(truncated)
        visible = text.replace("<b>", "").replace("</b>", "").split("<a ")[0] + "Batafsil o'qish →"
        self.assertLessEqual(tg._u16(visible), tg.CAPTION_LIMIT)

    def test_html_is_escaped(self):
        text, _ = tg.build_text(Post(title="<script>", content="a & b", slug="s"), 4096)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("a &amp; b", text)

    def test_linkedin_text_limit(self):
        text = linkedin.build_commentary(Post(title="T", content="so'z " * 2000), "https://misol.uz/blog/t/")
        self.assertLessEqual(len(text), linkedin.TEXT_LIMIT + 200)  # escape belgilari hisobga olinmaydi


class PageTests(TestCase):
    def test_pages_render(self):
        Post.objects.create(title="Salom dunyo", content="x")
        for url in ["/", "/blog/", "/blog/salom-dunyo/", "/ishlar/", "/robots.txt", "/sitemap.xml", "/maxfiylik/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_cyrillic_slug(self):
        self.assertEqual(Post.objects.create(title="Янги ўқув йили").slug, "yangi-oquv-yili")

    def test_future_post_hidden(self):
        Post.objects.create(title="Kelajak", published_at=timezone.now() + timedelta(days=1))
        self.assertEqual(self.client.get("/blog/kelajak/").status_code, 404)

    def test_connect_requires_staff(self):
        response = self.client.get("/connect/linkedin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
