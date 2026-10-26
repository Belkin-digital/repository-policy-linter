---
created: 2026-10-26
updated: 2026-10-26
---

# Применение линтера к собственному проекту

Дата: 26.10.2026. Проект: `/Users/aleksejbelkin/Git/repository-policy-linter`.

## Настройка

- Единственный policy config — [`.repo-policy.yaml`](../.repo-policy.yaml): 14 правил,
  в том числе наличие исходников, тестов, metadata/lockfile, AGENTS/CLAUDE, skill и CI/hook
  configuration; frontmatter skill; импорт AGENTS из CLAUDE; синтаксис JSON/YAML и newline.
- Python-проверки делегированы Ruff 0.14.2, без автоисправления. PyYAML 6.0.3,
  pre-commit 4.3.0 и остальные dev-зависимости зафиксированы в `uv.lock`.
- Собственный движок 0.1.0 устанавливается через `uv sync --frozen` из текущего checkout.
  Проверен путь импорта из `src/repo_policy`. Циклическая зависимость от ранее собранного
  wheel не добавлялась. В другие проекты движок по-прежнему ставится внешним пакетом.
- Локальный `.git/hooks/pre-commit` реально установлен. Его конфигурация
  [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) запускает policy на каждом коммите
  целиком (`always_run`), затем проверяет форматирование Python. Хуки не правят и не stage-ят файлы.
- Проверка всех файлов нужна и для коммитов, содержащих только удаления. Хук по одному
  списку добавленных/изменённых файлов может пропустить удаление обязательного документа.
  Соответствующий пример в установочном skill также исправлен.
- В GitHub Actions добавлен реальный `pre-commit run --all-files` вместе с существующими
  тестами, Ruff и policy check. Удалённый CI не запускался: remote пока не назначен.
- AGENTS содержит команды для Codex/Claude; существующий импорт из CLAUDE сохранён.
  Игнорируемый `work/` используется для временной проверки и кэшей.

## Проверки

В реальном проекте успешно выполнены:

```bash
uv sync --frozen
uv run --frozen repo-policy check --all --allow-plugins
uv run --frozen repo-policy check --changed --allow-plugins
uv run --frozen pre-commit validate-config
uv run --frozen pre-commit run --all-files
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv build
```

Результат: **0 нарушений** в all/changed; оба hook checks — Passed;
**33 теста** движка — OK; lint/format и сборка — успешно. Среда: macOS, Python 3.14.7.

Дополнительно в одноразовом Git-репозитории с копией текущих рабочих файлов и независимой
средой выполнены **15 сценариев**:

1. Чистый проект проходит собственную policy.
2. Пустой changed set успешно проходит с обязательными structural checks.
3. Отсутствующий newline даёт file/line/rule диагностику и exit 1.
4. `fix --dry-run` сохраняет исходные байты.
5. `fix` сохраняет Markdown hard-break spaces и CRLF; повторный fix — no-op.
6. Некорректный JSON отклоняется.
7. Реальный Ruff-плагин находит неиспользуемый Python import (F401).
8. Skill без YAML frontmatter отклоняется правилом `skill-metadata`.
9. Невалидный временный файл внутри `work/` не попадает в выборку.
10. Без `--allow-plugins` выполнение внешнего плагина блокируется с exit 2.
11. Повторная установка Git hook сохраняет его содержимое без дублирования.
12. Реальный `git commit` с плохим форматированием отклоняется; файл не изменяется хуком.
13. После исправления реальный `git commit` проходит оба hook checks.
14. Коммит, только удаляющий обязательный README, отклоняется policy hook.
15. Изначальная локальная конфигурация `docviewer.json` рабочего проекта сохранена
    без изменений (сравнён SHA-256 до/после проверки).

Машинный результат сценариев сохранён локально в `work/self-policy-verification.json`;
одноразовые репозитории удалены после проверки. Ошибочные файлы в рабочий проект не добавлялись.

## Повседневное использование

```bash
uv run --frozen repo-policy check --changed --allow-plugins
uv run --frozen repo-policy check --all --allow-plugins
uv run --frozen pre-commit run --all-files
uv run --frozen repo-policy fix --all --allow-plugins --dry-run
```

После просмотра dry-run можно убрать `--dry-run`, чтобы применить только разрешённые newline
fixes. Специализированные автоисправления через эти команды не запускаются. Другие реальные
репозитории и глобальные настройки агентов в этой работе не изменялись.
