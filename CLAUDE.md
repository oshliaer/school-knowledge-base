# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Назначение

Репозиторий хранит учебные материалы в формате Markdown и собирает из них `.apkg`-файлы для импорта в Anki/AnkiWeb.

Поток: **исходники в репо → `dist/*.apkg` → GitHub Release → AnkiWeb**

## Команды разработки

```bash
# Первый запуск — создать venv и установить зависимости
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# Собрать все колоды
.venv/bin/python scripts/md2anki.py

# Собрать одну колоду
.venv/bin/python scripts/md2anki.py "Вероятность и статистика 7-9"

# Указать нестандартную папку вывода
.venv/bin/python scripts/md2anki.py --output /tmp/anki
```

Результат — `dist/<Название_колоды>.apkg`.

## Структура репозитория

```
<Предмет>/                  # папка предмета (любое название)
  deck.yaml                 # имя колоды и стабильный Anki ID
  decks/
    01-тема/
      cards.md              # карточки темы
      images/               # картинки, на которые ссылаются карточки
    02-другая-тема/
      cards.md
scripts/
  build.py                  # конвертер md → .apkg
requirements.txt
.github/workflows/build.yml # CI/CD: сборка + публикация релиза
```

## Формат карточек (`cards.md`)

YAML frontmatter задаёт тип и теги для всего файла.
Карточки разделяются строкой `---` (с пустыми строками вокруг).

### Basic (вопрос / ответ)

```markdown
---
type: basic
tags: [тег1, тег2]
---

## Текст вопроса (лицевая сторона)

Текст ответа (обратная сторона).
Может быть **несколько абзацев** и ![картинка](images/img.png).

---

## Следующий вопрос

Следующий ответ.
```

### Basic-reversed (двусторонняя карточка)

```markdown
---
type: basic-reversed
tags: [термины]
---

## Термин

Определение термина.
```

Создаёт две карточки: термин→определение и определение→термин.

### Cloze (пропуск в тексте)

```markdown
---
type: cloze
tags: [формулы]
---

Площадь круга равна {{c1::π·r²}}.

---

{{c1::Медиана}} делит упорядоченный ряд пополам.
```

Тип `cloze` также определяется автоматически при наличии `{{c1::...}}` в тексте.

## deck.yaml

```yaml
id: 1748392650123456   # стабильный ID — не менять после первого импорта в Anki!
name: "Название колоды"
```

ID генерируется один раз. Если изменить — Anki создаст дубликат колоды.

## CI/CD

- **Push в `main`** → сборка + артефакт в GitHub Actions
- **Тег `v*`** → сборка + создание GitHub Release с `.apkg`-файлами
