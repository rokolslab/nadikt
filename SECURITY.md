# Политика Безопасности

## Поддерживаемые Версии

Публичного release Nadikt пока нет. Security fixes применяются к текущей ветке
`main` и активным pull requests. Disposable experiments не считаются
production-ready, но их data-loss и privacy defects также рассматриваются как
security issues.

## Как Сообщить Об Уязвимости

Не создавайте публичный issue, если сообщение содержит:

- способ вставить текст в неподтверждённое или защищённое поле;
- потерю/раскрытие clipboard, transcript, audio или dictionary data;
- выполнение команд, privilege escalation или обход integrity checks;
- credentials, private paths, window titles или пользовательский content.

Используйте приватную форму GitHub:

**[Report a vulnerability](https://github.com/rokolslab/nadikt/security/advisories/new)**

Если GitHub временно недоступен, не публикуйте exploit details в issue или
discussion; повторите отправку через private advisory после восстановления
сервиса.

## Что Указать

- затронутую revision/branch и операционную систему;
- минимальные шаги воспроизведения с synthetic data;
- ожидаемое и фактическое поведение;
- потенциальное влияние на confidentiality, integrity или availability;
- безопасный proof of concept без пользовательского payload.

Не прикладывайте реальные аудиозаписи, transcript, clipboard dumps,
screenshots с личными данными, model credentials или process dumps.

## Процесс Реагирования

Maintainer постарается:

1. подтвердить получение сообщения;
2. воспроизвести проблему в controlled environment;
3. определить severity и affected scope;
4. подготовить fix и regression check;
5. опубликовать advisory после устранения, если это необходимо.

Точные сроки ответа пока не гарантируются: проект не имеет production release
и формальной security team.

## Scope

В scope входят собственный код и документация этого репозитория. Уязвимости
Python, Windows, PySide6, ASR engines, models и других third-party components
следует также сообщать их upstream maintainers.
