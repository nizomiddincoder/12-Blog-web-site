"""Make.com scenariysi postni joylagach, uning ID va havolasini shu manzilga qaytaradi.

So'rov: POST /api/make/result/
Sarlavha: X-Make-Secret: <MAKE_RESULT_SECRET>
Tana (JSON): {"post_id": 12, "platform": "instagram", "external_id": "1789...", "url": "https://..."}
"""
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponseNotAllowed, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import PostDelivery

log = logging.getLogger("core.make")
ALLOWED = {"instagram", "youtube"}


@csrf_exempt
def make_result(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    secret = settings.MAKE_RESULT_SECRET
    given = request.headers.get("X-Make-Secret", "")
    if not secret or not hmac.compare_digest(given, secret):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)

    platform = str(data.get("platform", "")).lower()
    external_id = str(data.get("external_id", "")).strip()
    url = str(data.get("url", "") or "")[:500]
    try:
        post_id = int(data.get("post_id"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "post_id"}, status=400)
    if platform not in ALLOWED or not external_id:
        return JsonResponse({"ok": False, "error": "platform or external_id"}, status=400)

    delivery = PostDelivery.objects.filter(post_id=post_id, platform=platform).first()
    if not delivery:
        return JsonResponse({"ok": False, "error": "delivery not found"}, status=404)
    delivery.external_ids = [external_id]
    delivery.external_url = url
    delivery.status = PostDelivery.Status.SENT
    delivery.sent_at = delivery.sent_at or timezone.now()
    delivery.save(update_fields=["external_ids", "external_url", "status", "sent_at", "updated_at"])
    log.info("Make natijasi: post %s, %s, id %s", post_id, platform, external_id)
    return JsonResponse({"ok": True})
