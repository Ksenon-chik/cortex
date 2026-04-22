# Current Pitfalls and Risks

## 1. User API keys are stored without encryption

Это самый заметный текущий security debt. Пока ключи лежат в базе в открытом виде, production-grade доверие к системе ограничено.

## 2. Whitelist exists, but policy enforcement is incomplete

Флаг `whitelisted` и admin approve flow есть, однако его нужно рассматривать как частично реализованный механизм. Документация больше не должна описывать whitelist как полностью закрывающий доступ контур, пока это не подтверждено кодом end-to-end.

## 3. Scheduler deployment can duplicate work in the wrong runtime shape

Так как scheduler встроен в backend-приложение, нужно внимательно контролировать режим запуска. Несколько независимых backend-процессов без coordination могут привести к повторным resolution jobs.

## 4. Manual event import is a product decision, but also an operational bottleneck

Текущая схема хороша для quality control, но создаёт ручную нагрузку на админку. Если каталог событий вырастет, понадобится либо автоматизация, либо более сильная модерация потока.

## 5. Premium semantics are not fully expressed in UX and backend policy

План пользователя влияет на лимиты, но пока не формирует полностью отдельный опыт доступа к моделям. Это может создавать путаницу и в продукте, и в документации.

## 6. Repository hygiene still needs cleanup

В репозитории есть локальные артефакты окружения и сборки. Это не ломает продукт напрямую, но повышает шум, затрудняет ревью и мешает чётко отделять исходники от временных файлов.

## 7. External provider contracts may drift

Провайдеры моделей, Tavily и Polymarket могут менять ответы, лимиты и правила доступа. Любая документация по моделям и импортам должна опираться на текущий код и периодически пересматриваться.

## 8. Documentation drift is already a proven risk

Этот проект уже пережил фазу, когда README и research описывали заметно другую систему. Значит, обновление документации должно стать частью обычного цикла разработки, а не редкой «генеральной уборкой».
