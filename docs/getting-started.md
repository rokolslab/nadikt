[← Центр документации](README.md) · [К проекту](../README.md) · [Тестирование →](testing.md)

# Начало Работы

## Что Доступно Сейчас

Nadikt находится на стадии исследования и квалификации технических рисков.
Готового desktop-приложения, installer и production entry point пока нет.

В репозитории доступны:

- согласованные требования Windows MVP;
- Explicit Architecture и roadmap;
- исследования ASR-кандидатов и открытых приложений;
- disposable Windows insertion spike с automated tests.

## Требования К Окружению

Для чтения документации достаточно Git. Для automated experiment checks нужны:

| Компонент | Требование |
|---|---|
| ОС | Windows 10/11 x64 для real Win32 checks |
| Python | 3.12 x64 |
| Сеть | Не нужна для tests/runtime experiment |
| Внешние Python packages | Не нужны |

Общие будущие модули должны разрабатываться и на Ubuntu, но текущий Win32
experiment запускается только на Windows.

## Клонирование

```powershell
git clone https://github.com/rokolslab/nadikt.git
cd nadikt
```

Проверка состояния:

```powershell
git status
python --version
```

## Первый Automated Run

```powershell
cd experiments/windows_insertion
python -m unittest discover -s tests
```

Tests используют injected API facades и synthetic canaries. Они не должны
вводить текст в пользовательские приложения или менять реальный clipboard.

## Controlled Windows Check

```powershell
python fixtures/classic_target.py --self-check
```

Fixture создаёт собственные native `EDIT` и `ES_PASSWORD`, проверяет
foreground/focus перед input и завершает процесс с non-zero code при любом
нарушенном case.

## Что Не Запускать Без Подготовки

Manual CLI и clipboard racer предназначены для контролируемого experiment, а
не повседневного ввода. Перед использованием прочитайте:

- [experiment README](../experiments/windows_insertion/README.md);
- [результаты spike](research/windows_insertion_spike_results.md);
- [правила безопасности](../SECURITY.md).

## Следующий Шаг

Выберите задачу из [roadmap](../.ai-factory/ROADMAP.md), создайте отдельную
ветку и сверяйте поведение с ТЗ, а не только с `AGENTS.md` или AI-контекстом.

## См. Также

- [Тестирование](testing.md)
- [Участие в разработке](../CONTRIBUTING.md)
- [Стратегия разработки](architecture/Nadikt_development_strategy.md)
