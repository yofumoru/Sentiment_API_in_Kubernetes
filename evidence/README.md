# Результаты выполнения

Журналы записаны на локальном стенде. Календарные отметки в журналах и на отдельных скриншотах удалены. Показатели и ход эксперимента сохранены. Изображения
этапов установки, сборки, развёртывания и тестов показывают фактические
журналы или исходный код в локальном просмотрщике. Скриншоты Grafana и
Prometheus сняты с интерфейсов работающих служб.

| Этап | Журнал | Скриншот |
| --- | --- | --- |
| Установка Minikube и два узла Ready | [install-commands.log](install-commands.log), [cluster.log](cluster.log) | [install.jpg](install.jpg) |
| Maven, Dockerfile и образ на обоих узлах | [maven.log](maven.log), [image-build-retry.log](image-build-retry.log), [image-size.log](image-size.log) | [image.jpg](image.jpg), [source.jpg](source.jpg) |
| API, валидация и Actuator | [api-smoke.log](api-smoke.log) | [api.jpg](api.jpg) |
| Реплики, распределение запросов и внешние IP | [deploy.log](deploy.log), [routes.log](routes.log), [loadbalancer.log](loadbalancer.log) | [deployment.jpg](deployment.jpg) |
| Мониторинг и Helm | [monitoring.log](monitoring.log), [helm-list.log](helm-list.log) | [grafana.jpg](grafana.jpg), [prometheus.jpg](prometheus.jpg) |
| Нагрузка, HPA и финальная проверка | [hpa.log](hpa.log), [hpa-recovery.log](hpa-recovery.log), [final-status.log](final-status.log) | [hpa.jpg](hpa.jpg), [grafana.jpg](grafana.jpg) |

Первый запуск VirtualBox остановился на проверке VT-x, а профиль с
обходом проверки заработал. Второй узел добавлен отдельной командой.
Windows не позволила `minikube tunnel` добавить маршрут без повышения
прав. Для двух сервисов через Helm установлен MetalLB. Первое ожидание
Traefik закончилось по таймауту, повтор после выдачи IP прошёл.

Первый наблюдатель HPA дошёл до событий уменьшения и исчерпал своё
временное окно. Дополнительный журнал подтвердил три готовых пода.
Значения 617%, 529%, 480% и 7% в hpa.log выражены в процентах от CPU
request, равного 50m на под. Это не проценты полной ёмкости узлов.
