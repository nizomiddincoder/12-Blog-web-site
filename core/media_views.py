"""Media fayllarni tarqatish (Range so'rovlarini qo'llab-quvvatlaydi — videoni oldinga/orqaga
o'tkazish va iPhone/Safari'da video ijro etish uchun shart). Serverda bu ishni nginx qiladi."""
import os
import re

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils._os import safe_join

from .media_utils import guess_mime

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
CHUNK = 512 * 1024


def _iter_file(fh, length):
    try:
        remaining = length
        while remaining > 0:
            data = fh.read(min(CHUNK, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data
    finally:
        fh.close()


def serve_media(request, path):
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
    except Exception:
        raise Http404
    if not os.path.isfile(full_path):
        raise Http404

    size = os.path.getsize(full_path)
    content_type = guess_mime(full_path)
    match = RANGE_RE.match(request.headers.get("Range", "").strip())

    if match and (match.group(1) or match.group(2)):
        start_s, end_s = match.groups()
        if start_s == "":
            start, end = max(size - int(end_s), 0), size - 1
        else:
            start = int(start_s)
            end = min(int(end_s), size - 1) if end_s else size - 1
        if start >= size or start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        fh = open(full_path, "rb")
        fh.seek(start)
        length = end - start + 1
        response = StreamingHttpResponse(_iter_file(fh, length), status=206, content_type=content_type)
        response["Content-Length"] = str(length)
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    else:
        response = FileResponse(open(full_path, "rb"), content_type=content_type)

    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "public, max-age=604800"
    return response
