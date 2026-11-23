# Sentiment API в Kubernetes

Java 21, Spring Boot, Minikube, Traefik, Prometheus и Grafana. Приложение классифицирует текст по трём категориям: `positive`, `negative` и `neutral`. Например, `GET /api/sentiment?text=hello` возвращает `{"sentiment":"positive"}`.

- [Запуск готового стенда в PowerShell](#запуск-готового-стенда-в-powershell) — обычный сценарий на компьютере, где профиль уже настроен.
- [Проверка API и мониторинга](#проверка-api-и-мониторинга) — маршрутизация, Grafana и цели Prometheus.
- [Нагрузочный тест HPA](#нагрузочный-тест-hpa) — повтор эксперимента с автомасштабированием.
- [Развёртывание с нуля](#развёртывание-с-нуля) — установка проекта в новый кластер.
- [Результаты и выводы](#результаты-и-выводы) — измерения на проверенном стенде.

## Запуск готового стенда в PowerShell

Этот сценарий предназначен для компьютера, на котором уже существует настроенный профиль Minikube `sentiment-lab`. **Готовых виртуальных машин в репозитории нет.** После клонирования на другой компьютер стенд создаётся по разделу [«Развёртывание с нуля»](#развёртывание-с-нуля).

В портативной установке профиль хранится в `.local/.minikube/profiles/sentiment-lab/`, а диски VirtualBox — в `.local/.minikube/machines/sentiment-lab/disk.vmdk` и `.local/.minikube/machines/sentiment-lab-m02/disk.vmdk`. Каталог `.local` также содержит локальную конфигурацию и ключи. Он исключён из Git.

Команды выполняются в **PowerShell на Windows**. `$standRoot` — папка, содержащая `.local` настроенного стенда. Если стенд и репозиторий находятся в разных папках, в первой строке указывается абсолютный путь к папке стенда.

```powershell
$standRoot = (Get-Location).Path
$env:MINIKUBE_HOME = (Resolve-Path (Join-Path $standRoot '.local')).Path
$env:KUBECONFIG = Join-Path $env:MINIKUBE_HOME 'kubeconfig'
$mini = Join-Path $env:MINIKUBE_HOME 'minikube.exe'
if (-not (Test-Path -LiteralPath $mini -PathType Leaf)) {
    $mini = (Get-Command minikube.exe -ErrorAction Stop).Source
}
function ks { & $mini -p sentiment-lab kubectl -- @args }
```

Этот блок используется в каждом новом окне PowerShell. `ks` вызывает kubectl для профиля проекта. Для команд с путями `k8s/` и `scripts/` рабочим каталогом остаётся корень репозитория.

### Состояние и запуск

```powershell
& $mini -p sentiment-lab status
```

Если у обоих узлов указано `host: Running`, кластер уже работает. После остановки кластера или перезагрузки Windows используется существующий профиль:

```powershell
& $mini -p sentiment-lab start --driver=virtualbox --no-vtx-check --container-runtime=docker --preload=false
```

### Проверка готовности

```powershell
ks get nodes
ks -n sentiment rollout status deployment/sentiment --timeout=180s
ks -n sentiment get deployment,pods,svc,ingress,hpa
```

В штатном состоянии у двух узлов статус `Ready`, rollout завершается сообщением `deployment "sentiment" successfully rolled out`, а Deployment показывает `3/3` готовых реплик. Service `sentiment` имеет тип `LoadBalancer`, Ingress обслуживает `sentiment.test`, диапазон HPA составляет 3–8 реплик.

Остановка стенда с сохранением профиля:

```powershell
& $mini -p sentiment-lab stop
```

## Проверка API и мониторинга

### REST API, Ingress и балансировка

На проверенном стенде MetalLB назначил приложению `192.168.59.81`, а Traefik — `192.168.59.80`. На другой установке адреса могут отличаться. Команды используют IP из статуса служб:

```powershell
ks -n sentiment get svc sentiment
ks -n ingress-system get svc traefik
$appIp = ks -n sentiment get svc sentiment -o 'jsonpath={.status.loadBalancer.ingress[0].ip}'
$ingressIp = ks -n ingress-system get svc traefik -o 'jsonpath={.status.loadBalancer.ingress[0].ip}'

curl.exe -fsS "http://$appIp/api/sentiment?text=hello"
curl.exe -i -H "Host: sentiment.test" "http://$ingressIp/api/sentiment?text=hello"
```

Первый запрос возвращает `{"sentiment":"positive"}`. Второй проходит через Ingress и возвращает HTTP 200 с тем же JSON и заголовком `X-Instance`, содержащим имя пода. Проверка распределения по репликам:

```powershell
1..15 | ForEach-Object {
    curl.exe -fsS -D - -o NUL -H "Host: sentiment.test" "http://$ingressIp/api/sentiment?text=hello" |
        Select-String '^X-Instance:'
} | Group-Object Line | Select-Object Count, Name
```

Имена подов и ВМ отображаются в `ks -n sentiment get pods -l app=sentiment -o wide`. Если `EXTERNAL-IP` остаётся в состоянии `<pending>`, проверяется настройка MetalLB или туннеля. Для диагностики Ingress без внешнего IP в отдельном окне доступна команда `ks -n ingress-system port-forward svc/traefik 18080:80`. В таком случае адрес запроса — `http://127.0.0.1:18080/api/sentiment?text=hello` с заголовком `Host: sentiment.test`.

### Grafana и Prometheus

Если страница уже доступна, проброс порта работает. После перезагрузки Windows или закрытия консоли проброс создаётся заново. Каждая из команд выполняется в отдельном окне PowerShell с настройками из раздела запуска. Сообщение `Forwarding from 127.0.0.1:…` означает, что локальный адрес готов. Проброс действует, пока работает команда.

| Служба | Проброс порта | Страница |
| --- | --- | --- |
| Grafana | `ks -n monitoring port-forward svc/prometheus-grafana 13000:80` | [Дашборд Sentiment API](http://127.0.0.1:13000/d/sentiment-lab) |
| Prometheus | `ks -n monitoring port-forward svc/prometheus-kube-prometheus-prometheus 19090:9090` | [Targets](http://127.0.0.1:19090/targets) |

Данные для полей **Email or username** и **Password** в форме входа Grafana хранятся в Kubernetes Secret. Команды ниже выводят соответственно логин и пароль в локальную консоль:

```powershell
$secret = ks -n monitoring get secret prometheus-grafana -o json | ConvertFrom-Json
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($secret.data.'admin-user'))
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($secret.data.'admin-password'))
```

В Prometheus на странице **Targets** фильтр **Filter by endpoint or labels** со значением `sentiment-metrics` показывает цели приложения. При трёх готовых репликах ожидается `3 / 3 up`. Эквивалентная проверка на вкладке **Query**:

```promql
sum(up{namespace="sentiment",service="sentiment-metrics"})
```

Prometheus опрашивает Actuator по `/actuator/prometheus` каждые 15 секунд через отдельный Service на порту 8081. На дашборде доступны частота запросов, задержка p95, CPU на под, реплики HPA, распределение предсказаний и число доступных целей. Панель CPU использует cAdvisor и kube-state-metrics, а HPA получает данные из Metrics Server.

## Нагрузочный тест HPA

Для теста нужны три готовые реплики и числовое значение CPU в колонке `TARGETS`. Значение `<unknown>` означает, что метрика для HPA пока недоступна.

```powershell
ks -n sentiment get hpa
ks -n sentiment top pods -l app=sentiment
ks -n sentiment get job sentiment-load --ignore-not-found
```

При повторе эксперимента удаляется предыдущий тестовый Job `sentiment-load` со статусом `Complete`. При первом запуске Job ещё отсутствует. Скрипт сам создаёт новый Job и вызывает `kubectl.exe` из `PATH`. Блок для готового стенда добавляет клиент из кеша Minikube. Если клиент уже установлен и доступен через `PATH`, достаточно команды удаления старого Job и запуска скрипта. Рабочая директория — корень проекта, оболочка — PowerShell 7.

```powershell
ks -n sentiment delete job sentiment-load --ignore-not-found
$kubectl = Get-ChildItem (Join-Path $env:MINIKUBE_HOME '.minikube\cache') -Recurse -Filter kubectl.exe |
    Select-Object -First 1
$env:Path = "$($kubectl.DirectoryName);$env:Path"
.\scripts\watch-hpa.ps1
```

Три процесса Fortio отправляют запросы к API около трёх минут. Наблюдение продолжается до восьми минут, чтобы захватить снижение числа реплик после завершения нагрузки. Признаки успешного теста в консоли — строки `PASS: scale-up` и `PASS: scale-down -> 3 ready`. Фактический пик зависит от нагрузки и доступных ресурсов. Цель HPA — 60% от CPU request, который составляет `50m` на под. Окно стабилизации при уменьшении числа реплик — 60 секунд.

Для просмотра эксперимента на дашборде Grafana подходит диапазон **Last 15 minutes**. Основные панели — **«Запросы к API»**, **«CPU на под»** и **«Реплики HPA»**. Итоговое состояние и события также доступны в PowerShell:

```powershell
ks -n sentiment get job sentiment-load
ks -n sentiment get deployment,pods,hpa
ks -n sentiment describe hpa sentiment
ks -n sentiment logs -l job-name=sentiment-load --tail=15 --prefix
```

Ожидаемое итоговое состояние — Job `Complete` с `3/3` завершениями, Deployment с тремя готовыми репликами и события HPA `SuccessfulRescale`.

## Развёртывание с нуля

На Windows требуются [Minikube](https://minikube.sigs.k8s.io/docs/start/), VirtualBox и [Helm 3](https://helm.sh/docs/intro/install/). Все команды выполняются в **PowerShell на Windows из корня репозитория**. Команда `minikube start` с драйвером `virtualbox` и параметром `--nodes=2` создаёт две ВМ. Подготовку гостевых систем, Docker и Kubernetes выполняет Minikube.

| Где | Что выполняется |
| --- | --- |
| Windows | Запуск Minikube и VirtualBox, команды kubectl и Helm, редактирование YAML и HTTP-проверки. |
| ВМ `sentiment-lab` | Управляющий узел с API-сервером и планировщиком Kubernetes. На этом узле также могут выполняться поды приложения. |
| ВМ `sentiment-lab-m02` | Рабочий узел. Здесь выполняются поды, размещённые планировщиком. |
| На уровне кластера | Deployment создаёт три реплики приложения. Kubernetes размещает их по узлам. Helm устанавливает MetalLB, Traefik, Prometheus и Grafana. Minikube включает Metrics Server. |

Ручная настройка компонентов внутри ВМ для этого сценария не требуется. [Два узла Minikube](https://minikube.sigs.k8s.io/docs/tutorials/multi_node/) · [Драйвер VirtualBox](https://minikube.sigs.k8s.io/docs/drivers/virtualbox/)

### 1. Создание кластера

Профиль и kubeconfig сохраняются в `.local` внутри репозитория. `minikube.exe` и `helm.exe` доступны через `PATH` либо указываются абсолютными путями.

```powershell
$env:MINIKUBE_HOME = (New-Item -ItemType Directory -Force '.local').FullName
$env:KUBECONFIG = Join-Path $env:MINIKUBE_HOME 'kubeconfig'
$mini = (Get-Command minikube.exe -ErrorAction Stop).Source
function ks { & $mini -p sentiment-lab kubectl -- @args }

& $mini version
helm version --short
& $mini -p sentiment-lab start --driver=virtualbox --no-vtx-check --container-runtime=docker --preload=false --cpus=4 --memory=8192mb --nodes=2
ks get nodes -o wide
& $mini -p sentiment-lab addons enable metrics-server
ks -n kube-system rollout status deployment/metrics-server --timeout=180s
```

Ожидаются два узла со статусом `Ready`. На проверенном стенде использовались VirtualBox 7.2, Minikube 1.39.0 и Kubernetes 1.37.0. Если после прерванной установки в профиле остался один узел, второй добавляется командой `& $mini -p sentiment-lab node add`.

### 2. Сборка и загрузка образа на оба узла

Сборка запускается с Windows и выполняется в Docker внутри управляющей ВМ. Minikube сохраняет образ в локальный архив и загружает его в контейнерную среду обоих узлов. Это позволяет Kubernetes запускать реплики на любой из двух ВМ.

```powershell
& $mini -p sentiment-lab image build -t sentiment:1.0.0 .
& $mini -p sentiment-lab image save sentiment:1.0.0 .local/sentiment.tar
& $mini -p sentiment-lab image load .local/sentiment.tar
& $mini -p sentiment-lab ssh -- docker image inspect sentiment:1.0.0 --format '{{.Size}}'
& $mini -p sentiment-lab ssh --node sentiment-lab-m02 -- docker image inspect sentiment:1.0.0 --format '{{.Size}}'
```

Две последние команды выполняют проверку внутри соответствующих ВМ и выводят размер образа в байтах. В первой стадии Dockerfile Maven собирает Spring Boot JAR, а `jlink` создаёт компактный Java runtime. Финальная стадия содержит Alpine, runtime и JAR. [Команды работы с образами Minikube](https://minikube.sigs.k8s.io/docs/commands/image/)

### 3. Входящий трафик и Deployment

MetalLB назначает внешние IP службам приложения и Traefik в локальной сети VirtualBox между Windows и ВМ (host-only). Перед применением `k8s/metallb-virtualbox.yaml` проверяются адреса узлов и настройки DHCP:

```powershell
ks get nodes -o wide
$vbox = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
& $vbox list hostonlyifs
& $vbox list dhcpservers
```

В репозитории задан пул `192.168.59.80–192.168.59.81`. Если сеть отличается или эти адреса заняты, в `spec.addresses` объекта `IPAddressPool` указываются два свободных адреса из подсети ВМ вне DHCP. При использовании `minikube tunnel` вместо MetalLB туннель должен работать до установки Traefik. В Windows добавление маршрута для туннеля может потребовать прав администратора.

```powershell
helm repo add metallb https://metallb.github.io/metallb
helm repo add traefik https://traefik.github.io/charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install metallb metallb/metallb --version 0.16.2 -n metallb-system --create-namespace --set frr.enabled=false --set frrk8s.enabled=false --wait --timeout 5m
ks apply -f k8s/metallb-virtualbox.yaml
helm upgrade --install traefik traefik/traefik --version 42.4.1 -n ingress-system --create-namespace -f k8s/traefik-values.yaml --wait --timeout 8m

ks apply -f k8s/app.yaml
ks -n sentiment rollout status deployment/sentiment --timeout=180s
ks -n sentiment get deployment,pods,svc,ingress,hpa
ks -n sentiment get pods -l app=sentiment -o wide
```

В колонке `NODE` отображается ВМ каждого пода. На проверенном стенде одна реплика выполнялась на управляющем узле, две — на рабочем. [Журнал развёртывания](evidence/deploy.log)

При варианте с туннелем шаги установки MetalLB и применения его пула пропускаются. У Traefik и приложения проверяется назначение внешних IP, затем выполняются запросы из раздела проверки API.

### 4. Установка мониторинга

```powershell
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack --version 93.4.1 -n monitoring --create-namespace -f k8s/helm-values.yaml --wait --timeout 12m
ks wait --for=condition=Established crd/servicemonitors.monitoring.coreos.com --timeout=120s
ks apply -f k8s/monitoring.yaml
ks -n monitoring create configmap sentiment-dashboard --from-file=sentiment.json=k8s/dashboard.json --dry-run=client -o yaml |
    & $mini -p sentiment-lab kubectl -- apply -f -
ks -n monitoring label configmap sentiment-dashboard grafana_dashboard=1 --overwrite
ks -n monitoring get pods
```

ConfigMap обновляется тем же блоком с `--dry-run=client -o yaml` и `apply`. После развёртывания применяются те же проверки Grafana, Prometheus и HPA, что и на готовом стенде.

## Модель и контракт API

Мультиномиальная модель наивного Байеса с равными априорными вероятностями обучается при старте на 18 размеченных примерах из [sentiment.tsv](src/main/resources/sentiment.tsv). Слова выделяются по Unicode и приводятся к нижнему регистру. Для известных слов модель суммирует логарифмы условных вероятностей со сглаживанием Лапласа. Незнакомые слова пропускаются. При равенстве максимальных оценок сохраняется первый класс из порядка `neutral`, `positive`, `negative`.

Параметр `text` обязателен. Поддерживается от 1 до 2048 кодовых единиц UTF-16. Отсутствующий, пробельный или слишком длинный ввод возвращает HTTP 400. При наличии локальных Maven и JDK 21 или новее API можно проверить отдельно от Kubernetes через `mvn package` и `java -jar target/sentiment.jar`. В этом режиме API слушает порт 8080, Actuator — 8081.

## Результаты и выводы

| Проверка | Фактический результат | Материалы |
| --- | --- | --- |
| Кластер | Два узла `Ready`, в исходном состоянии три готовые реплики | [Кластер](evidence/cluster.log), [Deployment](evidence/deploy.log) |
| Размер образа | 100 427 815 и 100 429 835 байт на двух узлах, оба значения ниже 150 МБ | [Измерение образа](evidence/image-size.log) |
| REST API и маршрутизация | Проверены три класса и HTTP 400 для ошибочного ввода. Через прямой LoadBalancer и Ingress получен HTTP 200 | [Проверка API](evidence/api-smoke.log), [LoadBalancer](evidence/loadbalancer.log) |
| Балансировка | Из 15 запросов через Ingress каждый из трёх подов обработал по 5 | [Журнал запросов](evidence/routes.log) |
| Масштабирование | HPA прошёл цикл 3 → 7 → 8 → 3. Fortio получил 281 241 ответ HTTP 200 после прогрева | [Нагрузка](evidence/hpa.log), [Возврат к 3 репликам](evidence/hpa-recovery.log) |
| Мониторинг | После завершения теста Prometheus подтвердил три цели `UP` | [Финальное состояние](evidence/final-status.log), [Grafana](evidence/grafana.jpg), [Prometheus](evidence/prometheus.jpg) |

Ingress распределил запросы между исходными репликами, а HPA увеличил их число при росте CPU и вернул исходную ёмкость после нагрузки. Результаты относятся к локальному стенду и параметрам [Job Fortio](k8s/load.yaml). HTTP-проверки подтверждают контракт сервиса. Для оценки качества модели на других текстах нужен отдельный корпус, поскольку учебная модель использует частоты слов и не учитывает порядок слов, отрицания и иронию.

Исходники находятся в [src/main](src/main/), манифесты и дашборд — в [k8s](k8s/), полный перечень журналов и скриншотов — в [evidence/README.md](evidence/README.md).

## Материалы для сдачи

- [Отчёт, 10 страниц](output/pdf/report-sentiment-kubernetes.pdf) — анализ шести работ arXiv, архитектура, результаты и приложения.
- [Презентация, 10 слайдов](output/pdf/presentation-sentiment-kubernetes.pdf) — схема решения, результаты проверки и графики масштабирования.
