# Участие В Разработке Nadikt

Спасибо за интерес к проекту. Nadikt пока находится на стадии исследования и
квалификации рисков, поэтому небольшие проверяемые изменения предпочтительнее
широких реализаций без согласованного плана.

## Перед Началом

1. Прочитайте [README](README.md) и [центр документации](docs/README.md).
2. Сверьте поведение с [ТЗ](docs/requirements/Nadikt_TZ_v0.2.md).
3. Проверьте [roadmap](.ai-factory/ROADMAP.md) и открытые issues.
4. Для крупной функции сначала создайте issue с scope и acceptance criteria.

## Workflow

```powershell
git switch main
git pull origin main
git switch -c feature/short-description
```

- Не работайте напрямую в `main`.
- Один PR должен решать одну связанную задачу.
- Не смешивайте production code и disposable experiment без отдельного
  архитектурного решения.
- Не добавляйте backward compatibility без реального внешнего потребителя.

## Архитектурные Границы

- Domain/application core не импортирует PySide6, Windows API, SQLite details
  или конкретный ASR SDK.
- Platform objects не выходят за adapter boundary.
- ASR adapters не управляют UI, clipboard, dictionary или audio capture.
- Composition выполняется в явной точке сборки, а не через service locator.

См. [`.ai-factory/ARCHITECTURE.md`](.ai-factory/ARCHITECTURE.md).

## Privacy И Security

Никогда не добавляйте в Git, tests, logs или issues:

- пользовательское аудио и transcript;
- clipboard payload и filenames;
- пользовательский словарь;
- tokens, credentials и приватные model URLs;
- process/window titles и control content.

Используйте только synthetic fixtures. Уязвимости отправляйте по правилам
[SECURITY.md](SECURITY.md), а не через публичный issue.

## Tests

Для изменений Windows insertion spike:

```powershell
cd experiments/windows_insertion
python -m unittest discover -s tests
python -m compileall -q insertion_spike fixtures
```

Новые production modules должны получать unit/contract coverage вместе с
первым реальным use case. Подробнее: [docs/testing.md](docs/testing.md).

## Стиль Изменений

- Python names: `snake_case`; classes/protocols: `PascalCase`.
- Предпочитайте guard clauses и явные state transitions.
- Errors на внешних границах переводите в безопасные typed outcomes.
- Logs должны содержать только технические безопасные поля.
- Не создавайте пустые каталоги и speculative abstractions заранее.

## Коммиты

Используйте Conventional Commits:

```text
feat(asr): add local engine contract
fix(windows): reject changed target before dispatch
docs: clarify model package lifecycle
test(text): cover replacement ordering
```

## Pull Request Checklist

- Scope соответствует issue/плану.
- Tests и compile checks проходят.
- `git diff --check` проходит.
- Нет sensitive payload, binaries, model weights или generated dumps.
- Документация обновлена при изменении поведения/структуры.
- Все `NOT RUN` cases названы явно и не представлены как pass.
- Новые зависимости имеют версию, лицензию и обоснование.

## Лицензирование

Отправляя contribution, вы соглашаетесь лицензировать его на условиях
[MIT License](LICENSE). Не копируйте сторонний код без совместимой лицензии,
provenance и отдельного review.
