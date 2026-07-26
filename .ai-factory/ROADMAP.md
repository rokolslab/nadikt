# Roadmap Nadikt

> Автономный голосовой ввод для Windows 10/11 с переносимым Python-ядром, локальными ASR-движками и будущим Ubuntu adapter.

## Milestones

- [x] **Требования, архитектура и стратегия кодовой базы** - согласованы ТЗ v0.2, Explicit Architecture, стратегия разработки Windows/Ubuntu и решение `HYBRID` на основе технического и лицензионного исследования.
- [ ] **Квалификация критических технических рисков** - воспроизводимо сравнить GigaAM/faster-whisper и варианты VAD/segmentation на CPU, проверить bounded-memory long dictation и отдельно выполнить Windows insertion spike.
- [ ] **Переносимое ядро и консольный vertical slice** - реализовать независимый от ОС цикл capture -> segmentation -> ASR -> text assembly с engine contracts, нормализацией, словарём и автоматическими тестами.
- [ ] **Ранний Windows vertical slice** - подтвердить hotkey -> capture -> local ASR -> safe clipboard/insertion в Notepad, Word, browser и 1С до разработки полного desktop UI.
- [ ] **Windows desktop shell** - добавить PySide6 overlay без захвата focus, tray, настройки, выбор микрофона, сигналы, single instance, autostart и diagnostics.
- [ ] **Автономная поставка и model packages** - зафиксировать versioned package manifests, checksums, licenses, offline installer, dependency notices и rollback к работоспособной модели.
- [ ] **Windows MVP hardening и выпуск** - выполнить security/privacy checks, десятиминутную диктовку, CPU/RAM/latency protocol, application insertion matrix, installer/uninstaller tests и подготовку к signing.
- [ ] **Ubuntu version** - реализовать LinuxAdapter, отдельно проверить X11/Wayland hotkeys и insertion, добавить Linux packaging на базе общего ядра.

## Completed

| Milestone | Date |
|---|---|
| Требования, архитектура и стратегия кодовой базы | 2026-07-26 |
