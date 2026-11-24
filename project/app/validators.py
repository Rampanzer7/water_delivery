import os

from django.core.exceptions import ValidationError

MAX_IMAGE_SIZE = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
DANGEROUS_EXTENSIONS = {
    '.php', '.php3', '.php4', '.php5', '.phtml', '.phar', '.pht',
    '.exe', '.bat', '.cmd', '.sh', '.py', '.pl', '.cgi',
    '.js', '.vbs', '.msi', '.bin', '.jsp', '.jspx',
    '.asp', '.aspx', '.shtml', '.svg', '.jar', '.war',
    '.dll', '.so'
}


def looks_like_image(head):
    is_jpeg = head.startswith(b'\xff\xd8\xff')
    is_png = head.startswith(b'\x89PNG\r\n\x1a\n')
    is_webp = head[:4] == b'RIFF' and head[8:12] == b'WEBP'
    return is_jpeg or is_png or is_webp


def validate_image(file):
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError('Размер файла не должен превышать 2 МБ.')

    filename = getattr(file, 'name', '') or ''
    name_lower = filename.lower()
    parts = name_lower.split('.')

    # Защита от опасных двойных расширений (.php.jpg, .exe.png, .jsp.webp и др.)
    if len(parts) > 2:
        for middle_ext in parts[1:-1]:
            if f'.{middle_ext}' in DANGEROUS_EXTENSIONS:
                raise ValidationError(f'Файлы с опасными двойными расширениями (.{middle_ext}) запрещены.')

    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError('Допустимы только файлы JPG, PNG и WEBP.')

    file.seek(0)
    head = file.read(12)
    file.seek(0)
    if not looks_like_image(head):
        raise ValidationError('Содержимое файла не похоже на изображение.')

    # Глубокая проверка структуры файла через библиотеку Pillow
    try:
        from PIL import Image
        file.seek(0)
        with Image.open(file) as img:
            img.verify()
            fmt = (img.format or '').upper()
            if fmt not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValidationError('Содержимое файла не похоже на изображение.')

            # Проверка соответствия внутреннего формата файла его заявленному расширению
            ext_map = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}
            if ext_map.get(extension) != fmt:
                raise ValidationError(f'Формат содержимого файла ({fmt}) не соответствует расширению ({extension}).')
    except ValidationError:
        raise
    except Exception:
        raise ValidationError('Содержимое файла не похоже на изображение.')
    finally:
        file.seek(0)
