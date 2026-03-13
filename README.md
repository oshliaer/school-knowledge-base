# School Knowledge Base

Конвертация Markdown-карточек в колоды Anki (.apkg).

**Версия:** 1.0.0 | [Релизы](https://github.com/oshliaer/school-knowledge-base/releases)

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
│   ├── styles.css          # Стили карточек (опционально)
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

## Вопрос / лицевая сторона

^^^

Текст ответа / обратная сторона.

---

---
id: my-card-id       # явный id (обязательно!)
type: basic-reversed # переопределение типа
tags: [доп-тег]      # дополнительные теги
---

## Другой вопрос

^^^

Текст ответа.
```

**Обязательный разделитель `^^^`** отделяет вопрос от ответа только для типов `basic` и `basic-reversed`. Без него карточка пропускается при сборке. Для типа `cloze` этот разделитель не требуется.

### Типы карточек

- `basic` — вопрос/ответ
- `basic-reversed` — вопрос/ответ + ответ/вопрос (двусторонняя)
- `cloze` — карточка с закрытым текстом `{{c1::...}}`

## Стили карточек

Папка предмета может содержать файл `styles.css` для управления внешним видом карточек. Скрипт автоматически подбирает стили по названию папки предмета.

Пример `styles.css`:

```css
.card {
  font-family: 'Open Sans', sans-serif;
  font-size: 20px;
  line-height: 1.6;
}

table {
  border-collapse: collapse;
  margin: 1em 0;
}

table td, table th {
  border: 1px solid #ccc;
  padding: 0.5em;
}

hr {
  border: none;
  border-top: 2px solid #999;
  margin: 1em 0;
}
```

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
