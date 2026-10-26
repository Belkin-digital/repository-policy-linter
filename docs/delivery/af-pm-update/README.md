# Обновление концепта и бэклога Agent Factory

26.10.2026 изменения **применены** в существующий локальный репозиторий:

`/Users/aleksejbelkin/Git/Agent Factory Workspace/AF-PM`

Добавлены:

- [REQ_AF_005_repository-policy-webhook.md](REQ_AF_005_repository-policy-webhook.md) — требование владельца, переносимые правила и критерии приёмки.
- [IMP_AF_027_repository-policy-webhook.md](IMP_AF_027_repository-policy-webhook.md) — этапы платформенного внедрения и открытые решения.

В исходном AF-PM это `requirements/factory_AF/REQ_AF_005_repository-policy-webhook.md`
и `plan/improvements/IMP_AF_027_repository-policy-webhook.md`. Копии здесь предоставлены
для просмотра; относительные ссылки внутри них рассчитаны на структуру AF-PM.

Также обновлены `plan/SoW/SoW_AF_001_platform-concept.md`, `plan/SoW/README.md`,
`plan/improvements/README.md` и `requirements/REGISTRY.md` (штатным генератором реестра).
Итого шесть файлов. [Патч только этой работы](af-pm-update.patch) построен относительно
содержимого до изменений, включая уже имевшиеся пользовательские правки.

Проверены метаданные нового REQ, локальные ссылки и наличие в реестрах. Генератор plan
запущен в dry-run: он предложил также стороннюю нормализацию старых данных; этот вывод
не применялся. `plan/REGISTRY.md` остался байт-в-байт прежним.

Путь: локальные Claude/Codex → push/PR webhook → AF Runner на точном SHA →
наблюдательный check/status и сравнение результатов → явный переход к required gate.
Policy/toolchain сохраняются; платформенная проверка использует утверждённый baseline,
чтобы проверяемый PR не мог отключить собственные правила.

Это принятое требование и бэклог, а не развёрнутая функция AF. Tracker-тикет не создавался,
инкремент/срок не назначен. Платформенный код не менялся, AF-PM не коммитился и не пушился;
имевшиеся незакоммиченные изменения сохранены.
