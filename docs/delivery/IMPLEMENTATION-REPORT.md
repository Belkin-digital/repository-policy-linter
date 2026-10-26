# Repository Policy Linter — результат реализации

26 октября 2026 года. Создан **отдельный локальный Git-репозиторий**
[repository-policy-linter](../../README.md), ветка `main`.

Путь: `/Users/aleksejbelkin/Git/repository-policy-linter`

Начальный коммит: `efc0641597d6d49b66f2874d4b55a3ce906f9f8c`.
Remote не назначен; GitHub-репозиторий, PyPI-релиз и PR не создавались.

## Что реализовано

- Пакет `repository-policy-linter` **0.1.0**, Python 3.11+, одна runtime-зависимость — PyYAML.
- `repo-policy check`, `fix`, `explain`, `init`; JSON/текст, file/line/column/rule/severity/message;
  коды 0 — чисто, 1 — нарушения, 2 — ошибка запуска/конфигурации, 130 — прерывание.
- All/changed/explicit files, Git merge-base, staged/unstaged/untracked, исключения с причинами,
  детерминированная сортировка и строгая версия YAML-конфига.
- Девять базовых видов правил: required/forbidden paths, required/forbidden text, размер файла,
  финальный newline, синтаксис JSON/YAML, обязательные ключи данных и Markdown frontmatter.
- Внешние специализированные проверки как локальные плагины: native Ruff JSON, общий JSON
  и regex для существующих parsable-форматов. Реальная интеграция Ruff проверена на самом проекте.
- `fix` только добавляет перевод строки в явно разрешённых правилах; не обрезает Markdown
  пробелы, не запускает сторонние автоисправления, отказывается от symlink/hardlink-записей.
- Устанавливаемый `repo-policy-setup` skill для Codex/Claude, консервативный helper, installer,
  инструкции по зависимостям, pre-commit, CI и AGENTS/CLAUDE. Движок не копируется в целевой repo.
- `repo-policy-af`: Runner CLI bridge с тем же движком/правилами и JSON-отчётом;
  отдельный output fragment для существующего AF result manifest, без автоматической публикации.
- Документация, lockfile, тесты, pre-commit и GitHub Actions CI.

## Структура

```text
repository-policy-linter/
├── src/repo_policy/              # CLI, engine, config, selection, rules, plugins, AF bridge
├── skills/repo-policy-setup/     # SKILL.md, helper, reference, starter policy
├── scripts/                     # skill installer, isolated wheel/setup verification
├── tests/                       # 33 теста
├── docs/                        # конфигурация, плагины, AF assessment/backlog, release
├── .github/workflows/ci.yml
├── .repo-policy.yaml
├── .pre-commit-config.yaml
├── pyproject.toml / uv.lock
└── dist/                        # собранные wheel и исходный архив; исключены из Git
```

## Запуск и установка

Из папки исходного репозитория:

```bash
uv sync --frozen --no-editable
uv run --frozen --no-editable repo-policy check --all --allow-plugins
uv run --frozen --no-editable python -m unittest discover -s tests -v
```

`--allow-plugins` здесь разрешает прочитанный локальный Ruff-плагин проекта. В новом
starter config внешние команды отсутствуют и этот флаг не требуется.

Установить skill агенту, затем открыть **выбранный** целевой репозиторий:

```bash
REPO_POLICY_SOURCE='/Users/aleksejbelkin/Git/repository-policy-linter'
python3 "$REPO_POLICY_SOURCE/scripts/install_skill.py" --destination "$HOME/.agents/skills/repo-policy-setup"
# Для Claude Code вместо этой команды выбрать соответствующее расположение:
python3 "$REPO_POLICY_SOURCE/scripts/install_skill.py" --destination "$HOME/.claude/skills/repo-policy-setup"
```

В Codex вызвать `$repo-policy-setup`, в Claude Code — `/repo-policy-setup`, указав выбранный
репозиторий и реально собранный wheel 0.1.0. Skill создаёт/согласует `.repo-policy.yaml`,
фиксирует внешнюю зависимость и интеграции, затем запускает проверки и тесты целевого проекта.
В существующем repo helper по умолчанию только показывает план; `--apply` создаёт отсутствующие
файлы и сохраняет существующие. Локальный `file://` источник wheel подходит для пилота;
для платформенного исполнения нужен общий доступный immutable artifact URL/wheelhouse.

Wheel можно установить обычным pip в отдельную среду выбранного проекта. Пока пакет не
опубликован, не использовать одно лишь имя пакета как доказательство доступности этой сборки.
Полный [быстрый старт и команды](../../README.md).

## Выполненные проверки

Локально на macOS / Python **3.14.7** успешно выполнены:

1. **33 теста**: Git selections, renames/deletions/unborn HEAD, diagnostics/thresholds,
   YAML/JSON/aliases/duplicates, file bounds, symlink/hardlink/path handling,
   безопасный fix/dry-run, плагины (успех/невалидный вывод/timeout/ошибки), CLI, AF parity и setup.
2. Ruff lint и format check — все 14 Python-файлов прошли.
3. Собственный `repo-policy check --all --allow-plugins` — 0 диагностик.
4. pre-commit validation и реальный `pre-commit run --all-files` — Passed.
5. `skill-creator` validator — Skill is valid.
6. Сборка wheel/sdist и проверка их состава: в wheel только движок; skill включён в source archive.
7. Установка wheel в чистую среду без editable/source imports; `check → fix → check` прошли.
8. Полный путь распространения в изоляции: установка skill → preview → apply в тестовом repo →
   повторный apply без изменений → установка внешней pinned wheel dependency → успешный check.
   Исходники движка в целевой repo не копировались.
9. AF-PM: метаданные нового требования, ссылки и обновление requirements registry проверены.
10. Git whitespace checks прошли; новый repo после коммита чистый.

GitHub CI настроен для Linux Python 3.11–3.14 и Windows 3.12; удалённый CI ещё не запускался,
так как remote отсутствует. Windows-специфичная проверка здесь не выдаётся за выполненную.

## Agent Factory и новый запрос про webhook

Реально прочитаны локальные AF-PM/SoW/архитектурные контракты и backend schemas/run preparation.
[Подробное исследование и адаптер](../../docs/agent-factory.md) содержит
источники, HEAD и hashes прочитанных рабочих файлов. У исходных репозиториев были незакоммиченные
изменения; наличие кода в рабочей папке не названо фактом production deployment.

Подтверждены immutable SkillVersion/AgentVersion, `instructions_markdown`, Resource grants,
Core Policy/Approval/Audit, runtime snapshot, scoped `AF_SKILL_*` execution context и отдельный
platform executor. Файловый SKILL.md не выдан за зарегистрированный native AF skill;
несуществующий `protocol: shell` не придуман. Runner bridge проверяется локально на равенство
отчётов; deployed AF E2E остаётся отдельным шагом.

По прямому запросу владельца **применены** точечные изменения в AF-PM: **REQ_AF_005**,
**IMP_AF_027**, концепт/индекс SoW, индекс improvements и реестр requirements — шесть файлов.
Существующие правки сохранены. [Отчёт и применённый task-only patch](af-pm-update/README.md).

Концепция: локальный Claude/Codex → push/PR event → trusted exact SHA → детерминированный
Runner check с теми же policy/toolchain → наблюдательный status и сравнение → явно выбранный
required gate. Зафиксированы approved policy baseline, подпись/RBAC, dedup/retry, stale-head
защита, изоляция fork/plugin execution и публикация статуса проверенному SHA.
Webhook/platform checks ещё не реализованы; Tracker-тикет и инкремент не создавались.

## Артефакты и ограничения

- [Готовый wheel](../../dist/repository_policy_linter-0.1.0-py3-none-any.whl),
  SHA-256 `f2066eca1198fda84e3a9ed249396e0f0b6fdc4b50123ade05ba017f8d535923`.
- [Исходный архив](../../dist/repository_policy_linter-0.1.0.tar.gz),
  [контрольные суммы](artifact-checksums.json).
- [Устанавливаемый skill](../../skills/repo-policy-setup/SKILL.md).
- [Правила конфигурации](../../docs/configuration.md),
  [безопасность](../../SECURITY.md),
  [платформенный backlog](../../docs/platform-backlog.md).

Core не отправляет файлы в сторонние сервисы. Загрузка зависимостей при установке может
требовать сеть; плагины наследуют полномочия/окружение пользователя и не являются sandbox.
Платформа должна запускать недоверенные проверки в отдельной изоляции. YAML aliases,
multi-document YAML, custom tags и не-UTF-8 text не поддерживаются; regex не является
семантическим анализатором и требует доверенной конфигурации. Очень длинные file sets для
плагинов пока ограничены системным argv; ошибки исполнения не маскируются под clean.

Интеграция проверялась в одноразовых тестовых репозиториях. Реальные целевые repo для
пилотного внедрения ещё не выбраны; engine/skill глобально не устанавливались.
