# School Knowledge Base

Конвертация Markdown-карточек в колоды Anki (.apkg).

## Быстрый старт

```bash
# Установка зависимостей
pip install -r requirements.txt

# Сборка всех колод
python scripts/md2anki.py

# Сборка конкретной темы
python scripts/md2anki.py "Вероятность и статистика 7-9"
```

## Структура проекта

```
.
├── scripts/
│   └── md2anki.py          # Скрипт конвертации
├── <Предмет>/
│   ├── deck.yaml           # Конфигурация колоды (name, id)
│   └── decks/
│       ├── 00-тема.md      # Карточки напрямую в .md файлах
│       └── 01-тема.md
└── dist/                   # Выходные .apkg файлы
```

## Формат карточек

Файл карточек начинается с YAML frontmatter (опционально):

```markdown
---
type: basic          # basic | basic-reversed | cloze
tags: [тег1, тег2]   # теги по умолчанию для файла
---

## Заголовок карточки

Текст ответа.

---

---
id: my-card-id       # явный id (обязательно!)
type: basic-reversed # переопределение типа
tags: [доп-тег]      # дополнительные теги
---

## Другая карточка

Текст ответа.
```

### Типы карточек

- `basic` — вопрос/ответ
- `basic-reversed` — вопрос/ответ + ответ/вопрос
- `cloze` — карточка с закрытым текстом `{{c1::...}}`

## Скрипты и команды

| Команда | Описание |
|---------|----------|
| `python scripts/md2anki.py` | Собрать все колоды |
| `python scripts/md2anki.py "Название темы"` | Собрать одну колоду |
| `python scripts/md2anki.py --output dist/` | Указать выходную директорию |

## Требования

- Python 3.11+
- Зависимости: `genanki`, `markdown`, `PyYAML`, `python-slugify`

## CI/CD

GitHub Actions автоматически собирает колоды при пуше в ветку `master` и создаёт релиз по тегу `v*`.
