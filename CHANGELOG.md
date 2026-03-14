## [1.3.1] — 2026-03-14

### Изменено
- `requirements.txt`: уточнена минимальная версия `Pillow>=10.0.0`
- `scripts/fetch_flags.py`: `OVERSIZED` переработан из `object()` в singleton-класс `_Oversized` с `__repr__`
- `scripts/fetch_flags.py`: `resize_raster()` переименована в `_resize_raster()` (приватный API)
- `scripts/md2anki.py`: возвращаемый тип `build_subject()` уточнён как `Path | None`
- `scripts/md2anki.py`: добавлено логирование пропущенных папок без `decks/` (CSV-пайплайн и другие)

### Исправлено
- `scripts/fetch_flags.py`: при обновлении флага старый PNG не удаляется, если имя совпадает с новым (защита от случайного удаления)
- `География мира/countries.csv`: обновлены данные

## [1.3.0] — 2026-03-14

### Добавлено
- `scripts/fetch_flags.py`: новый файл `flags.csv` (отдельный cache) — хранит связь `wikidata_id → country_flag_file, capital_flag_file`
- `scripts/fetch_flags.py`: sentinel `OVERSIZED` — если SVG уже в кэше и больше `MAX_FLAG_SIZE`, PNG скачивается напрямую без повторной загрузки SVG
- `scripts/fetch_flags.py`: параметр `key_url` в `download_flag()` — имя файла считается от оригинального URL даже при скачивании PNG fallback
- `scripts/csv2anki.py`: join с `flags.csv` по `wikidata_id` при сборке колоды
- `География мира/overrides.yaml`: документация поля `exclude: true` для исключения несуверенных территорий

### Изменено
- `scripts/fetch_countries.py`: переработан SPARQL-запрос — заменён фильтр `P297` (ISO-код) на `wdt:P31/wdt:P279* wd:Q3624078` (суверенное государство) + `P297`. Исключает зависимые территории, оставляет де-факто государства (Тайвань, Палестина)
- `scripts/fetch_countries.py`: добавлены колонки `iso_code` (ISO 3166-1) и `un_member` (boolean)
- `scripts/fetch_countries.py`: удалены колонки `country_flag_file` и `capital_flag_file` из выходного CSV (перенесены в `flags.csv`)
- `scripts/fetch_flags.py`: теперь пишет в отдельный `flags.csv` вместо обновления `countries.csv`
- `scripts/fetch_flags.py`: `MAX_FLAG_SIZE` снижена до 100 КБ (было 350 КБ)
- `scripts/fetch_flags.py`: улучшено логирование — показывает размер SVG до и после resizing
- `География мира/countries.csv`: обновлён для новой архитектуры — 195 суверенных государств (было 239), новые колонки `iso_code`/`un_member`, удалены `*_flag_file`
- `География мира/overrides.yaml`: добавлены записи `Q35` (Дания): `un_member: true` (исправление Wikidata) и `Q1410` (Гибралтар): `exclude: true` (ошибочно классифицирован как суверенное государство)

### Удалено
- Флаги больше не встроены в `countries.csv` — перемещены в отдельный кэш `flags.csv`

### Закрыто
- GitHub #13: несуверенные территории в колоде География мира

## [1.2.0] — 2026-03-14

### Добавлено
- `scripts/fetch_flags.py`: лимит размера SVG `MAX_FLAG_SIZE = 350 КБ` — для больших SVG скачивается PNG-рендер с Wikimedia (`?width=300`) через `_png_fallback_url()`
- `scripts/fetch_flags.py`: авторесайз PNG/JPEG через Pillow — max height 300px (2x retina) через `_resize_raster()`
- `scripts/fetch_flags.py`: поддержка JPEG (`image/jpeg`) в `_fetch_url()`
- `scripts/fetch_flags.py`: поддержка `.jpg` в orphan-cleanup и `resolve_cached()`
- Новые функции в `fetch_flags.py`: `_fetch_url()`, `_png_fallback_url()`, `_resize_raster()`
- Счётчик размера при fallback: сообщение показывает исходный размер SVG и размер итогового PNG (e.g., `SVG слишком большой (594 КБ → PNG 300px, 18 КБ)`)

### Изменено
- `scripts/fetch_flags.py`: счётчик `missing` переименован → `limited` (большие SVG уже не \"отсутствуют\", а ограничены размером)
- `requirements.txt`: добавлен `Pillow` для обработки растровых изображений
- `.github/workflows/notify-telegram.yml`: рефакторинг многострочного сообщения — текст передаётся через env var `TG_MESSAGE` и файл `/tmp/tg_msg.txt`; curl использует `--data-urlencode "text@/tmp/tg_msg.txt"` и флаг `-g` для отключения URL-globbing (исправляет ошибки с `[` и `\"` в markdown-ссылках)
- `География мира/overrides.yaml`: добавлены ручные переопределения флагов для Q142 (Франция/Париж) и Q32 (Люксембург/Люксембург) — использованы флаги городов вместо флагов стран

## [1.1.1] — 2026-03-14

### Исправлено
- `scripts/md2anki.py`: папки без `decks/` теперь пропускаются (return None) вместо падения с ошибкой — добавлена совместимость с CSV-колодами в том же репозитории
- `.github/workflows/build.yml`: переименован шаг "Build decks" → "Build Markdown decks", добавлен шаг "Build CSV decks" с вызовом `csv2anki.py`

## [1.1.0] — 2026-03-13

### Добавлено
- Фильтр исторических государств в `fetch_countries.py` — в SPARQL-запрос добавлен `FILTER NOT EXISTS { ?country wdt:P576 [] }` для исключения ликвидированных государств (ГДР, СССР, Югославия и т.д.)
- Автоматическая очистка orphan-файлов флагов в `fetch_flags.py` — после записи CSV удаляются файлы из `flags/`, которые не упоминаются ни в колонке `country_flag_file`, ни в `capital_flag_file`

## [1.0.2] — 2026-03-13

### Добавлено
- Скрипт `.github/scripts/build_tg_message.py` — формирует текст Telegram-сообщения с заголовком (тег релиза) и отдельными ссылками на скачивание для каждой колоды (имя из `deck.yaml`, slug из имени `.apkg`-файла)

### Изменено
- Workflow `.github/workflows/notify-telegram.yml`: переработан на приём готового текста (`message`) вместо `tag`+`repository`
- Workflow `.github/workflows/build.yml`: добавлен шаг "Build Telegram message", который вызывает `build_tg_message.py` и передаёт результат в job `notify` через output

## [1.0.1] — 2026-03-13

### Добавлено
- Новый reusable workflow `.github/workflows/notify-telegram.yml` для отправки уведомлений в Telegram при выпуске релиза

### Изменено
- Workflow `.github/workflows/build.yml`: добавлен job `notify`, который вызывает `notify-telegram.yml` после успешной сборки при пуше тага
- `Вероятность и статистика 7-9/styles.css`: уменьшен `font-size` с `20px` до `14px`; добавлен явный `color: #333` для `th` (заголовки таблиц) для читаемости в ночном режиме Anki

## [1.0.0] — 2026-03-13

### Добавлено
- Новый обязательный разделитель `^^^` между вопросом и ответом в карточках `basic`/`basic-reversed` (без него карточка пропускается при сборке)
- Карточки параграфа «Таблицы» для темы ВиС 7-9 (01-таблицы.md, 01-таблицы-задачи.md)
- Правила создания карточек в CLAUDE.md (id, формат, ограничения для ВиС 7-9)
- Поддержка разделителя `^^^` в скрипте md2anki.py
- HTML-таблицы вместо изображений в карточках
- Файл `styles.css` в папке предмета для управления стилями карточек (шрифты, таблицы, отступы)

### Изменено
- Формат карточек `basic`/`basic-reversed` с явным разделением вопроса и ответа через `^^^` (breaking change)
- Форматирование карточек предисловия (выразительный markdown)
- Формат ID карточек: `{номер}-{тема}-{slug}`
- Скрипт md2anki.py: проверка ID карточек
- Скрипт md2anki.py: CSS теперь читается из файла `styles.css` в папке предмета
- Скрипт md2anki.py: нормализация CRLF при чтении файлов карточек
- Скрипт md2anki.py: разделитель `^^^` ищется через regex (допускаются пробелы и вариации)
- CLAUDE.md: примеры обновлены (добавлены `^^^`, явные `id`); уточнено, что `^^^` используется только для типов `basic` и `basic-reversed`
- Карточки 01-таблицы.md: обобщены формулировки (убраны узкие отсылки к мебели/Елене)

### Удалено
- Поддержка старого формата карточек `basic`/`basic-reversed` без разделителя `^^^` (breaking change)

> ⚠️ **Breaking change:** переписаны `id` всех карточек — колоды из версии 0.x несовместимы с 1.0.0. При повторном импорте Anki воспримет их как новые карточки — весь прогресс повторений будет сброшен. Рекомендуется удалить старую колоду перед импортом.

## [0.1.2] — 2026-03-12

### Исправлено
- `make_id()`: `hexdigest()[:15]` → `[:13]` — IDs теперь < 2^53, устраняет NPE при прямом импорте в AnkiDroid (Java `JSONObject` парсит большие числа как `double`, теряя точность)

> ⚠️ **Миграция:** из-за изменения `make_id()` автоматически генерируемые IDs колод и моделей изменились. При повторном импорте `.apkg` Anki может создать дубликат колоды вместо обновления. Рекомендуется удалить старую колоду перед импортом, **либо** зафиксировать `id` в `deck.yaml` вручную (число ≤ 9007199254740991).

## [0.1.1] — 2026-03-12

### Добавлено
- Транслитерация названий колод в имена файлов (кириллица → ASCII) через `python-slugify`
- Зависимость `python-slugify>=8.0.0` в `requirements.txt`

### Изменено
- Имена выходных файлов теперь строчные через дефис: `veroiatnost-i-statistika-7-9.apkg`
- Ручная таблица транслитерации (~20 строк) полностью удалена в пользу `python-slugify`

## [0.1.0] — 2026-03-12

### Добавлено
- Скрипт `scripts/md2anki.py` для конвертации Markdown-карточек в Anki (.apkg)
- Поддержка явных `id` для каждой карточки
- CSS со шрифтом Open Sans для карточек
- Переопределение `type`/`tags` для отдельных карточек
- GitHub Actions workflow для автоматической сборки по тегу `v*`

### Изменено
- Переименован скрипт: `scripts/build.py` → `scripts/md2anki.py`
- Изменена структура: файлы карточек теперь напрямую в `decks/*.md` (вместо папок `decks/*/cards.md`)
- Ветка в workflow изменена с `main` на `master`

### Удалено
- Скрипт `scripts/build.py` (заменён на `md2anki.py`)
