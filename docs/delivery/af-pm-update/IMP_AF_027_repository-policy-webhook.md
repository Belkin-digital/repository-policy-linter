# IMP_AF_027 — Переносимый repository linter и проверка по push/PR hook

**Статус:** backlog; требование владельца принято 26.10.2026, реализация платформы не начата.
**Источник:** [REQ_AF_005_repository-policy-webhook.md](../../requirements/factory_AF/REQ_AF_005_repository-policy-webhook.md).
**Концепция:** [SoW_AF_001_platform-concept.md](../SoW/SoW_AF_001_platform-concept.md).
**Tracker:** не создан; инкремент и сроки не назначены.

## Пользовательский сценарий

Пользователь продолжает работать локально в Claude/Codex с `.repo-policy.yaml`.
После push или обновления PR AF проверяет точный commit тем же линтером и правилами,
показывает сравнимый отчёт, сначала без блокировки. После приёмки тот же контроль
применяется к платформенному агенту и по явному выбору становится required check.

## Текущий результат и границы

В отдельном локальном репозитории `repository-policy-linter` подготовлен CLI-пакет
0.1.0, установочный agent skill и `repo-policy-af` Runner bridge. Платформенный код,
webhook intake, публикация GitHub checks и native SkillVersion этим не реализованы.
Публичный remote/registry URL линтера пока отсутствует. CLI bridge не заменяет native
Skill lifecycle и не копирует движок в рабочие репозитории.

## Этапы

1. Выбрать пилотный repo и общий immutable engine/toolchain; сохранить policy и locks.
2. Добавить deterministic Runner job с тем же CLI и JSON diagnostics; локальный parity harness.
3. Подключить доверенный push/PR intake к существующим identity/Resource/RBAC и очереди job;
   проверять подпись, delivery id и точный SHA; не подменять SHA движущейся веткой.
4. Добавить approved policy baseline и отдельную проверку candidate policy; исключить самообход
   gate изменением YAML/плагинов в проверяемом PR. Изолировать fork/untrusted execution.
5. Публиковать минимальный SHA-bound check/status и разрешённый report; dedup/retry,
   cancellation/superseded head и восстановление после ошибок должны быть тестируемыми.
6. Запустить observation, собрать mismatch evidence и устранить drift среды/выборки.
7. По отдельному выбору repo/веток включить required checks; предусмотреть rollback в observation.
8. При необходимости добавить native tool через поддерживаемый live AF protocol и Core lifecycle;
   не выдумывать `protocol: shell`, endpoints и операции установки из файлового SKILL.md.

## Критерии готовности

Полные AC — в [REQ_AF_005_repository-policy-webhook.md](../../requirements/factory_AF/REQ_AF_005_repository-policy-webhook.md).
Особое покрытие: local/Runner parity; поддельный/replayed event; повторная доставка и crash retry;
out-of-order heads; policy bypass; forks без секретов; timeout/missing tool/history; публикация
статуса ровно проверенному SHA; отключение enforce без потери правил.

## Открытые вопросы для проектирования

- Пилотные repo/ветки и владелец review policy/toolchain?
- Реальные deployed webhook/checks contracts и права GitHub App?
- Где хранится общий immutable wheel/toolchain, какой Runner image/revision используется?
- Какой существующий deterministic job slot/Artifact indexing path переиспользуем?
- Как фиксируем approved policy SHA/digest и принимаем её обновление?
- Какой порог parity/период observation достаточен для перехода к enforce?

Подробный дизайн и декомпозиция Tracker нужны отдельно; статус backlog не равен готовности
или включению в согласованный инкремент. Контрактные scope этим пунктом не менялись.
