import os

from django.core.exceptions import ValidationError

MAX_IMAGE_SIZE = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def looks_like_image(head):
    is_jpeg = head.startswith(b'\xff\xd8\xff')
    is_png = head.startswith(b'\x89PNG\r\n\x1a\n')
    is_webp = head[:4] == b'RIFF' and head[8:12] == b'WEBP'
    return is_jpeg or is_png or is_webp


def validate_image(file):
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError('Размер файла не должен превышать 2 МБ.')
    extension = os.path.splitext(file.name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError('Допустимы только файлы JPG, PNG и WEBP.')
    file.seek(0)
    head = file.read(12)
    file.seek(0)
    if not looks_like_image(head):
        raise ValidationError('Содержимое файла не похоже на изображение.')
