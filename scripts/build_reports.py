from pathlib import Path
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
import re

from PIL import Image
from pypdf import PdfWriter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output' / 'pdf'
OUT.mkdir(parents=True, exist_ok=True)
EVIDENCE = ROOT / 'evidence'
for name, file in [('Arial', 'arial.ttf'), ('ArialBold', 'arialbd.ttf'), ('Consolas', 'consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / file)))

INK = '#142537'
MUTED = '#486477'
TEAL = '#0B716C'
PAPER = '#F4F8F8'
WHITE = '#FFFFFF'
DARK = '#102A38'
MINT = '#91E2CE'
PALE = '#DBF3EF'
LINE = '#CCDDE1'
REPORT = (595.28, 841.89)
DECK = (960, 540)
PAPERS = [
    ('1', 'Fu и др., 2024', 'ServerlessLLM', '2401.14351v2', 'Локальные контрольные точки, перенос запросов, размещение по времени старта.'),
    ('2', 'Sui и др., 2025', 'ServerlessLoRA', '2505.14468v1', 'Общие веса и предварительная загрузка артефактов LoRA.'),
    ('3', 'Punniyamoorthy и др., 2025', 'SLO Driven Autoscaling', '2512.23415', 'Многосигнальное масштабирование Kubernetes с учётом SLO и стоимости.'),
    ('4', 'Wang и др., 2025', 'SchedMate', '2510.03334', 'Планирование GPU-задач с оценками из кода, логов и истории.'),
    ('5', 'Srivatsa и др., 2024', 'Preble', '2407.00023v2', 'Диспетчеризация LLM-запросов с переиспользованием KV-кэша.'),
    ('6', 'Zhou и др., 2026', 'SDQN / SDQN-n', '2601.13579', 'Размещение подов с помощью DQN. Дополнение за пределами 2024–2025 гг.'),
]
DOCS = [
    ('Minikube. Установка и создание кластера', 'https://minikube.sigs.k8s.io/docs/start/'),
    ('Minikube. Docker-драйвер и особенности WSL2', 'https://minikube.sigs.k8s.io/docs/drivers/docker/'),
    ('Kubernetes. Horizontal Pod Autoscaling', 'https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/'),
    ('Traefik. Установка в Kubernetes с Helm', 'https://doc.traefik.io/traefik/getting-started/kubernetes/'),
    ('Prometheus Operator. ServiceMonitor', 'https://prometheus-operator.dev/docs/developer/getting-started/'),
    ('Kubernetes. Прекращение поддержки ingress-nginx', 'https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/'),
]


def read(name):
    path = EVIDENCE / name
    return path.read_text(encoding='utf-8-sig', errors='replace').strip() if path.exists() else ''


def lines(name, select=None, count=14):
    result = read(name).splitlines()
    if select:
        result = [line for line in result if re.search(select, line)]
    return '\n'.join(result[:count])


def status(name, token):
    return token in read(name)


def text(c, value, x, y, width, size=11, leading=None, color=INK, font='Arial'):
    style = ParagraphStyle('text', fontName=font, fontSize=size, leading=leading or size * 1.36,
                           textColor=colors.HexColor(color), splitLongWords=True)
    p = Paragraph(value, style)
    _, height = p.wrap(width, 1000)
    p.drawOn(c, x, y - height)
    return y - height


def fill(c, color, x, y, width, height):
    c.setFillColor(colors.HexColor(color))
    c.rect(x, y, width, height, fill=1, stroke=0)


def rule(c, x, y, width, color=LINE):
    c.setStrokeColor(colors.HexColor(color))
    c.line(x, y, x + width, y)


def link(label, url):
    return f'<link color="{TEAL}" href="{url}">{escape(label)}</link>'


def block(c, title, body, y, x=50, width=495):
    y = text(c, escape(title), x, y, width, 14, color=TEAL, font='ArialBold') - 6
    return text(c, escape(body), x, y, width, 11.2, 16) - 19


def code(c, title, body, x, top, width, size=8.25, max_lines=15):
    label_y = text(c, escape(title), x, top, width, 9.8, color=MUTED, font='ArialBold')
    cleaned = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', body).replace('\ufeff', '')
    rows = cleaned.splitlines()[:max_lines] or ['Данные отсутствуют.']
    line_height = size + 4
    height = len(rows) * line_height + 20
    y = label_y - 7
    fill(c, DARK, x, y - height, width, height)
    c.setFont('Consolas', size)
    c.setFillColor(colors.HexColor('#E1F4F2'))
    for index, row in enumerate(rows):
        row = row.replace('\t', '  ')
        while pdfmetrics.stringWidth(row, 'Consolas', size) > width - 22:
            row = row[:-2] + '…'
        c.drawString(x + 11, y - 15 - index * line_height, row)
    return y - height - 16


def image(c, name, x, top, width, max_height, trim=1):
    path = EVIDENCE / name
    if not path.exists():
        return top
    with Image.open(path) as source:
        area = source.crop((0, 0, source.width, round(source.height * trim)))
    graphic = ImageReader(area)
    iw, ih = graphic.getSize()
    ratio = min(width / iw, max_height / ih)
    c.drawImage(graphic, x + (width - iw * ratio) / 2, top - ih * ratio,
                width=iw * ratio, height=ih * ratio)
    return top - ih * ratio - 12


def report_head(c, number, section, title, subtitle):
    fill(c, WHITE, 0, 0, *REPORT)
    fill(c, TEAL, 0, REPORT[1] - 7, REPORT[0], 7)
    text(c, 'SENTIMENT API  /  ИТОГОВЫЙ ПРОЕКТ', 50, 806, 495, 9, color=MUTED, font='ArialBold')
    text(c, escape(section.upper()), 50, 770, 495, 11, color=TEAL, font='ArialBold')
    y = text(c, escape(title), 50, 748, 495, 28, 34, font='ArialBold') - 9
    y = text(c, escape(subtitle), 50, y, 495, 11.7, 16, color=MUTED) - 22
    rule(c, 50, 44, 495)
    text(c, f'Локальный стенд     /     {number:02d} из 10', 50, 34, 495, 8.4, color=MUTED)
    return y


def box(c, name, x, y, w, h, color=PALE, size=9.5):
    fill(c, color, x, y, w, h)
    text(c, escape(name), x + 8, y + h - 8, w - 16, size, size * 1.16, font='ArialBold')


def arrow(c, x1, y1, x2, y2, color=TEAL):
    import math
    c.setStrokeColor(colors.HexColor(color))
    c.setLineWidth(1.1)
    c.line(x1, y1, x2, y2)
    angle = math.atan2(y2 - y1, x2 - x1)
    for delta in (-0.48, 0.48):
        c.line(x2, y2, x2 - 5 * math.cos(angle + delta), y2 - 5 * math.sin(angle + delta))


def architecture(c, x, top, scale=1):
    c.saveState()
    c.translate(x, top)
    c.scale(scale, scale)
    box(c, 'HTTP-клиент', 0, -42, 91, 42)
    box(c, 'Traefik Ingress /api', 109, -42, 109, 42)
    box(c, 'Service LoadBalancer', 236, -42, 117, 42)
    box(c, 'Deployment Java × 3', 371, -42, 124, 42)
    for a, b in [(91, 109), (218, 236), (353, 371)]:
        arrow(c, a, -21, b, -21)
    box(c, 'Grafana', 0, -112, 91, 40, PAPER)
    box(c, 'Prometheus', 109, -112, 109, 40, PAPER)
    box(c, 'ServiceMonitor → :8081', 236, -112, 117, 40, PAPER)
    box(c, 'HPA / Metrics Server', 371, -112, 124, 40, PAPER)
    arrow(c, 109, -92, 91, -92)
    arrow(c, 236, -92, 218, -92)
    arrow(c, 353, -77, 398, -42)
    arrow(c, 460, -72, 460, -42)
    c.restoreState()
    return top - 112 * scale - 24


image_pass = status('image-size.log', 'PASS:')
routes_up = status('routes.log', 'PASS:')
monitoring_up = status('monitoring.log', 'PASS:')
scaled = status('hpa.log', 'PASS: scale-up')
scaled_down = status('hpa.log', 'PASS: scale-down') or status('hpa-recovery.log', 'PASS: scale-down')
load_balancer_up = status('loadbalancer.log', 'PASS:')

def writer_with_metadata(path):
    writer = PdfWriter(clone_from=path)
    metadata = {key: value for key, value in writer.metadata.items()
                if key not in ('/Author', '/CreationDate', '/ModDate')}
    metadata['/Author'] = 'Егор Мешко'
    metadata['/Producer'] = 'ReportLab / pypdf'
    writer.metadata = metadata
    return writer


def add_attachments(path):
    archive = BytesIO()
    with ZipFile(archive, 'w', ZIP_DEFLATED) as zip_file:
        for name in ('README.md', 'Dockerfile', 'pom.xml', '.dockerignore'):
            zip_file.write(ROOT / name, name)
        for folder in ('evidence', 'k8s', 'src'):
            for file in sorted((ROOT / folder).rglob('*')):
                if file.is_file():
                    zip_file.write(file, file.relative_to(ROOT).as_posix())
    writer = writer_with_metadata(path)
    writer.add_attachment('attachments-sentiment.zip', archive.getvalue())
    with path.open('wb') as destination:
        writer.write(destination)

def stage(done, yes, no):
    return yes if done else no


def make_report():
    path = OUT / 'report-sentiment-kubernetes.pdf'
    c = canvas.Canvas(str(path), pagesize=REPORT)
    c.setTitle('Итоговый проект. Анализ тональности текста в Kubernetes')
    y = report_head(c, 1, 'Введение', 'Анализ тональности в Kubernetes', 'Разработка модели, контейнерное развёртывание, маршрутизация и мониторинг REST API.')
    y = block(c, 'Цель проекта', 'Создать REST API анализа тональности и развернуть три реплики. Проверить, что запросы доходят до разных экземпляров, Prometheus собирает показатели, а HPA меняет число реплик при росте загрузки ЦП.', y)
    y = block(c, 'Обучение локально при старте', 'Мультиномиальный наивный Байес получает 18 размеченных документов из ресурсов JAR, по шесть на класс. Частоты слов по классам преобразуются в логарифмы условных вероятностей со сглаживанием Лапласа. Априорные вероятности равны.', y)
    y = block(c, 'Инференс', 'Строка разбивается на последовательности букв Unicode. Для каждого класса складываются логарифмы вероятностей известных слов. Класс с наибольшей суммой попадает в JSON. Вне словаря признаки игнорируются. При полном равенстве побеждает neutral.', y)
    y = code(c, 'Фактическая проверка локального Java-процесса', lines('api-smoke.log', 'hello|horrible|meeting|missing|PASS', 5), 50, y, 495, 8.7)
    y = image(c, 'api.jpg', 50, y, 495, 114, trim=0.70)
    block(c, 'Границы проверки', 'HTTP-тест проверяет формат ответа и характерные примеры. Учебный корпус мал, токенизация не учитывает порядок слов, отрицание и иронию. Для оценки качества нужен отдельный корпус с macro-F1 и матрицей ошибок.', y)
    c.showPage()

    y = report_head(c, 2, 'Архитектура', 'Трафик и контуры управления', 'API и технические endpoints разделены портами и службами.')
    y = architecture(c, 50, y)
    y = block(c, 'Маршрутизация и балансировка', 'Ingress принимает запросы к sentiment.test с префиксом /api. Traefik получает готовые endpoints прикладного Service. Служба типа LoadBalancer также даёт прямой вход через IP MetalLB. Заголовок X-Instance определяет ответивший под. В 15 запросах через Ingress получено по пять ответов от каждой из трёх реплик.', y)
    y = block(c, 'Реплики и готовность', 'Deployment начинает с трёх реплик. Мягкое ограничение topologySpreadConstraints учитывает распределение по узлам. Startup, readiness и liveness используют Actuator. Контейнер запускается от UID 10001 без повышенных привилегий.', y)
    y = block(c, 'Масштабирование', 'HPA autoscaling/v2 получает CPU из Metrics Server. Запрос одного пода равен 50m, 60% от запроса соответствует примерно 30m. Число реплик ограничено интервалом 3–8, снижение стабилизируется 60 секунд. CPU на графике Grafana служит для диагностики.', y)
    block(c, 'Компромисс демонстрационного стенда', 'Прямой LoadBalancer и Ingress дают два пути проверки. Для внешней эксплуатации выбор точки входа, TLS и параметры доступности нужно согласовать с требованиями среды. В лаборатории технические endpoints отданы отдельному ClusterIP на 8081.', y)
    c.showPage()

    y = report_head(c, 3, 'Развёртывание', 'От JAR до кластера', 'Кластер и контейнер верифицируются по выводу команд. Полные журналы находятся в evidence/.')
    y = block(c, 'Подготовка среды', 'Windows 10, VirtualBox 7.2, Minikube 1.39.0 и Kubernetes 1.37.0. Профиль sentiment-lab содержит управляющий и рабочий узлы. VirtualBox выделил по 4 vCPU, 8192 МиБ управляющему узлу и 4050 МиБ добавленному worker. Версии Helm-чартов зафиксированы в README.', y)
    y = block(c, 'Многостадийная сборка', 'Maven упаковывает JAR, jlink создаёт компактный Java runtime. Dockerfile копирует их в Alpine. Один образ с общим ID загружен на оба узла. Измеренный Docker размер около 100,4 МБ на каждом узле.', y)
    measured = [row.split()[0] for row in read('image-size.log').splitlines()
                if re.match(r'^\d+ sha256:', row)]
    size_rows = '\n'.join(f'{node}: {size} bytes' for node, size in
                           zip(('sentiment-lab', 'sentiment-lab-m02'), measured))
    y = code(c, 'Docker image inspect sentiment:1.0.0', lines('maven.log', 'BUILD SUCCESS', 1) +
             '\n' + size_rows + '\n' + lines('image-size.log', 'PASS:', 1), 50, y, 495, 8.5)
    y = block(c, 'Диагностика Windows', 'VirtualBox сообщил об ошибке VT-x при активном гипервизоре. Запуск прошёл после --no-vtx-check и --preload=false, второй узел добавлен node add. При первой сборке Minikube исключил Dockerfile из контекста. Исправление .dockerignore позволило собрать образ.', y)
    y = block(c, 'Доступ из Windows', stage(load_balancer_up, 'Tunnel потребовал повышенных прав. MetalLB назначил 192.168.59.81 приложению и 192.168.59.80 Traefik. Через оба входа получен HTTP 200. После назначения IP Helm подтвердил готовность Traefik.', 'Для внешнего IP нужен локальный LoadBalancer.'), y)
    image(c, 'install.jpg', 50, y, 243, 110, trim=0.77)
    image(c, 'image.jpg', 302, y, 243, 110, trim=0.55)
    c.showPage()

    y = report_head(c, 4, 'Мониторинг', 'Метрики и эксперимент HPA', 'Дашборд связывает пользовательскую нагрузку, время отклика и число реплик.')
    y = block(c, 'Подключение метрик', 'ServiceMonitor выбирает Service sentiment-metrics и опрашивает /actuator/prometheus каждые 15 секунд. Micrometer публикует гистограмму HTTP-времени и счётчики по трём классам. Grafana получает дашборд из ConfigMap и использует источник Prometheus.', y)
    y = block(c, 'Опыт с нагрузкой', 'Нагрузка создавалась тремя процессами Fortio. Запросы передавались через Service в течение трёх минут. После прогрева зарегистрирован 281 241 ответ HTTP 200. HPA поднялся с 3 до 7, затем до 8 реплик. После нагрузки, обновления метрик и окна стабилизации кластер вернулся к 3 готовым репликам и 3 целям UP.', y)
    y = text(c, 'Grafana · запросы, p95, CPU и реплики во время эксперимента', 50, y, 495, 9.8, color=MUTED, font='ArialBold') - 6
    y = image(c, 'grafana.jpg', 50, y, 495, 210, trim=0.75)
    y = text(c, 'Prometheus · три цели UP после снятия нагрузки', 50, y, 495, 9.8, color=MUTED, font='ArialBold') - 6
    y = image(c, 'prometheus.jpg', 50, y, 495, 110, trim=0.92)
    text(c, 'Диагностика. Docker cAdvisor отдал CPU на уровне cgroup пода. После уточнения PromQL панель показала загрузку на под. Полные журналы приведены во вложении.', 50, y, 495, 9.7, 13, color=MUTED)
    c.showPage()

    y = report_head(c, 5, 'Анализ трендов / 1 из 3', 'Корпус исследования', 'Пять работ 2024–2025 годов и одна дополнительная работа 2026 года о Kubernetes-планировании с RL.')
    y = block(c, 'Метод отбора', 'Поиск на arXiv начат с запроса «AI Kubernetes containerization 2024-2025», затем уточнялся по трём темам. Из первичных работ отбирались конкретные методы и сравнения с базовыми решениями. Числа приведены в контексте задач авторов.', y)
    fill(c, DARK, 50, y - 28, 495, 28)
    text(c, 'Работа и год', 60, y - 8, 194, 10, color=WHITE, font='ArialBold')
    text(c, 'Подход', 266, y - 8, 269, 10, color=WHITE, font='ArialBold')
    y -= 28
    for index, (num, authors, name, arxiv, theme) in enumerate(PAPERS):
        fill(c, PAPER if index % 2 == 0 else WHITE, 50, y - 49, 495, 49)
        text(c, link(f'[{num}] {name}', f'https://arxiv.org/abs/{arxiv}'), 60, y - 8, 193, 10.3, font='ArialBold')
        text(c, escape(authors), 60, y - 25, 193, 9.8, color=MUTED)
        text(c, escape(theme), 266, y - 8, 266, 9.8, 13.1)
        rule(c, 50, y - 49, 495)
        y -= 49
    block(c, 'Основания для сравнения', 'Авторы измеряют разные объекты: запуск модели, время первого токена, длительность GPU-задачи, нарушения SLO и загрузку узлов. Сводить эти эффекты в единую шкалу было бы некорректно. Подходы сопоставлены по сигналам и уровню управления.', y - 22)
    c.showPage()

    y = report_head(c, 6, 'Анализ трендов / 2 из 3', 'Бессерверный ИИ и локальность', 'При работе с крупными моделями стоимость запуска включает перемещение весов и повторное вычисление состояния.')
    y = block(c, '[1] ServerlessLLM', 'Fu и соавторы размещают контрольные точки рядом с GPU и загружают их по уровням памяти. Диспетчер оценивает состояние хранилищ и ожидаемое время старта, а перенос активного инференса позволяет использовать подходящий сервер. Авторы сообщают о снижении задержки в 10–200 раз в своих сценариях сравнения с другими serverless-системами.', y)
    y = block(c, '[2] ServerlessLoRA', 'Sui и соавторы рассматривают сценарий множества LoRA-адаптеров. Они переиспользуют веса базовой модели, заранее подготавливают артефакты и учитывают конкуренцию процессов за GPU. В версии 2025 года на промышленных нагрузках авторы сообщают о снижении TTFT до 86% и стоимости до 89%. Результаты зависят от совместимости адаптеров и состава трафика.', y)
    y = block(c, '[5] Preble', 'Srivatsa и соавторы направляют запросы с общими префиксами на GPU, где уже есть соответствующее состояние модели. Политика учитывает очередь, чтобы локальность кэша не перегружала отдельный ускоритель. Авторы сообщили о снижении p99 в 2–10 раз на двух открытых LLM. Эффект зависит от повторяемости префиксов и распределения нагрузки.', y)
    y = block(c, 'Что проверить на Kubernetes', 'Для нейросетевой версии полезно сравнить прогретый пул и Knative или KServe со scale-to-zero. Отдельно измерить загрузку образа, загрузку модели, готовность пода и время первого успешного запроса. Кэширование модели требует проверки целостности версии и доступного места на узлах.', y)
    block(c, 'Применимость к учебному сервису', 'У локального байесовского классификатора небольшой корпус встроен в JAR. В этом случае сначала стоит измерить время JVM и readiness, а затем оценивать отдачу от прогрева или отключения простаивающих реплик.', y)
    c.showPage()

    y = report_head(c, 7, 'Анализ трендов / 3 из 3', 'Ресурсы, прогноз и RL', 'Масштабирование подов, выбор узла и диспетчеризация запросов решают разные задачи.')
    y = block(c, '[3] SLO и стоимость как сигналы управления', 'Punniyamoorthy и соавторы добавляют внешний слой управления Kubernetes. Алгоритм учитывает прикладные сигналы, возможность размещения подов и ограничения бюджета. В опубликованном эксперименте длительность нарушений SLO снизилась до 31%, время реакции улучшилось на 24%, затраты снизились на 18%. Для воспроизведения важны профиль нагрузки, правила расчёта стоимости и конфигурация базового HPA.', y)
    y = block(c, '[4] Семантика GPU-задач', 'SchedMate извлекает признаки из кода, логов и истории задач и дополняет Ray-планировщик. На физическом стенде из 8 узлов по 8 GPU среднее время завершения задач сократилось на 23,2% относительно Lucid. Оценка совета занимала в среднем 9 секунд. Подход подходит для длительных задач, где время принятия решения мало относительно полезной работы.', y)
    y = block(c, '[6] Планирование с подкреплением', 'Zhou и соавторы сравнивают SDQN и SDQN-n с kube-scheduler на вычислительных подах. Вариант SDQN-n допускает консолидацию. Авторы сообщают о снижении средней загрузки CPU на узел более чем на 20% для SDQN-n. Для вывода об экономии энергии понадобились бы замеры мощности при сопоставимых времени выполнения и объёме работы.', y)
    y = block(c, 'Практическое продолжение эксперимента', 'Базовый вариант — CPU-HPA. Следующий эксперимент может сравнить его с масштабированием по длине очереди или p95 через адаптер метрик. Нагрузки следует повторять с одинаковой трассой. Меры сравнения — доля времени выше порога задержки, число реплика-минут и время восстановления.', y)
    block(c, 'Условия для RL', 'В симуляции можно задать состояние из очереди и свободных ресурсов, действие как выбор допустимого узла и награду за пропускную способность с штрафом за нарушения SLO. Перед онлайн-использованием нужны сравнение с kube-scheduler и проверка на новых профилях.', y)
    c.showPage()

    y = report_head(c, 8, 'Заключение и ссылки', 'Итоги и источники', 'Аналитические выводы опираются на первичные публикации. Результаты стенда подтверждаются только фактическими артефактами.')
    y = block(c, 'Достижения', 'Собран Java-сервис с обучаемой моделью. Образ около 100,4 МБ работает в двухузловом Minikube. Проверены прямой LoadBalancer, распределение запросов через Ingress, сбор метрик и цикл HPA 3 → 8 → 3. Репозиторий и материалы проекта хранятся локально.', y)
    y = block(c, 'Перспективы', 'Для крупной модели критичны локальность весов и время запуска. На малом сервисе логичнее начать с наблюдения p95 и сравнения двух простых политик масштабирования на одинаковом потоке запросов.', y)
    y = text(c, 'Первичные работы arXiv', 50, y, 495, 13, color=TEAL, font='ArialBold') - 9
    for num, authors, name, arxiv, _ in PAPERS:
        y = text(c, link(f'[{num}] {authors} — {name} · arXiv:{arxiv}', f'https://arxiv.org/abs/{arxiv}'), 50, y, 495, 10.4, 14) - 5
    y -= 13
    y = text(c, 'Документация', 50, y, 495, 13, color=TEAL, font='ArialBold') - 9
    for label, url in DOCS:
        y = text(c, link(label, url), 50, y, 495, 10.4, 14) - 5
    c.showPage()

    y = report_head(c, 9, 'Приложения', 'Код, YAML и доказательства', 'Полные исходники, манифесты, журналы и скриншоты находятся во вложенном архиве attachments-sentiment.zip и в каталоге проекта.')
    controller = (ROOT / 'src/main/java/edu/project/sentiment/SentimentController.java').read_text(encoding='utf-8-sig')
    y = code(c, 'Приложение A. REST-контракт и счётчик', '\n'.join(controller.splitlines()[24:33]), 50, y, 495, 8.2)
    hpa = (ROOT / 'k8s/app.yaml').read_text(encoding='utf-8-sig').split('kind: HorizontalPodAutoscaler')[1]
    y = code(c, 'Приложение Б. Фрагмент HPA', 'kind: HorizontalPodAutoscaler\n' + '\n'.join(row for row in hpa.splitlines() if re.search('minReplicas|maxReplicas|scaleDown|stabilizationWindowSeconds|name: cpu|averageUtilization', row)), 50, y, 495, 8.2)
    code_bottom = image(c, 'source.jpg', 50, y, 211, 150, trim=0.93)
    deployment_bottom = image(c, 'deployment.jpg', 273, y, 272, 150, trim=0.95)
    y = min(code_bottom, deployment_bottom)
    y = image(c, 'hpa.jpg', 50, y, 495, 105, trim=0.51)
    text(c, 'Готовность Deployment и ответы Ingress/LoadBalancer приведены на снимке развёртывания. События SuccessfulRescale и финальная проверка ресурсов есть в журналах HPA.', 50, y, 495, 9.7, 13, color=MUTED)
    c.showPage()
    y = report_head(c, 10, 'Приложения', 'Проверка локального стенда', 'Команды и фактические результаты в конце нагрузочного эксперимента.')
    y = block(c, 'Готовность Kubernetes', 'Профиль sentiment-lab содержит управляющий и рабочий узлы. После стабилизации HPA Deployment вернулся к трём готовым репликам. Снимок состояния сохранён в evidence/final-status.log.', y)
    y = code(c, 'Узлы и Deployment', '$ kubectl get nodes\n' +
             lines('cluster.log', 'Ready', 2) + '\n' +
             '$ kubectl -n sentiment get deployment,pods,svc,ingress,hpa\n' +
             lines('final-status.log', r'deployment.apps/sentiment\s+3/3', 1),
             50, y, 495, 8.5)
    y = block(c, 'Маршрутизация', 'По прямому адресу приложения и по маршруту Traefik получен HTTP 200. Для Traefik запрос содержал Host: sentiment.test. По заголовкам X-Instance зафиксировано распределение 5/5/5 между исходными подами.', y)
    y = code(c, 'Проверка внешних IP', lines('loadbalancer.log', '^GET |^PASS:', 3), 50, y, 495, 8.5)
    y = block(c, 'Состояние мониторинга после нагрузки', 'Prometheus подтвердил три доступные цели приложения. Текущее и желаемое число реплик HPA составило 3. CPU для HPA поставляет Metrics Server.', y)
    code(c, 'Результаты запросов к Prometheus', lines('final-status.log', r'replicas.*: 3|sum\(up', 3), 50, y, 495, 8.2)
    c.showPage()
    c.save()
    add_attachments(path)


def slide_head(c, number, title, subtitle):
    fill(c, WHITE, 0, 0, *DECK)
    fill(c, TEAL, 0, 532, 960, 8)
    title_bottom = text(c, escape(title), 56, 487, 850, 35, 39, font='ArialBold')
    subtitle_bottom = text(c, escape(subtitle), 56, title_bottom - 12, 850, 16, 21, color=MUTED)
    rule(c, 56, 38, 848)
    text(c, f'Sentiment API в Kubernetes   /   {number:02d}', 56, 26, 848, 9.6, color=MUTED)
    return subtitle_bottom - 28


def column(c, title, body, x, y, width=390):
    y = text(c, escape(title), x, y, width, 20, 24, TEAL, 'ArialBold') - 10
    return text(c, escape(body), x, y, width, 17.2, 24) - 27


def make_deck():
    path = OUT / 'presentation-sentiment-kubernetes.pdf'
    c = canvas.Canvas(str(path), pagesize=DECK)
    c.setTitle('Защита проекта. Анализ тональности в Kubernetes')
    fill(c, DARK, 0, 0, *DECK)
    fill(c, MINT, 60, 461, 64, 5)
    text(c, 'ИТОГОВЫЙ ПРОЕКТ', 60, 442, 800, 14, color=MINT, font='ArialBold')
    text(c, 'Анализ тональности<br/>в Kubernetes', 58, 391, 806, 61, 66, WHITE, 'ArialBold')
    text(c, 'Java REST API · Minikube · Prometheus и Grafana', 60, 222, 800, 23, 30, '#B8DBDE')
    text(c, 'Локальный стенд', 60, 64, 800, 12, color=MINT)
    c.showPage()

    y = slide_head(c, 2, 'Цель и среда выполнения', 'Классифицировать текст и проверить, как Kubernetes обслуживает API при росте нагрузки.')
    y1 = column(c, 'Сервис', 'Java 21, Spring Boot, три класса тональности, русские и английские примеры из встроенного корпуса.', 56, y)
    column(c, 'Инфраструктура', 'Windows и Minikube, Docker, Helm, Traefik, Metrics Server, Prometheus и Grafana.', 56, y1)
    y2 = column(c, 'Приёмка', 'Контейнер до 150 МБ, три реплики, вход через /api, запись метрик и рост реплик под нагрузкой.', 503, y)
    column(c, 'Воспроизведение', 'Исходники, манифесты, дашборд и команды диагностики хранятся в локальном проекте.', 503, y2)
    c.showPage()

    y = slide_head(c, 3, 'Архитектура', 'Traefik маршрутизирует HTTP, а HPA и Prometheus получают метрики из отдельных источников.')
    y = architecture(c, 56, y - 9, 1.7)
    text(c, 'MetalLB выдаёт локальные IP. X-Instance показывает, какой под ответил.', 56, y - 12, 845, 17, 24)
    c.showPage()

    y = slide_head(c, 4, 'Модель и REST API', 'Мультиномиальный наивный Байес обучается при старте на 18 размеченных примерах.')
    column(c, 'Как получается ответ', 'Сервис выделяет слова, суммирует логарифмы условных вероятностей и выбирает лучший из трёх классов. Незнакомые слова пропускаются.', 56, y, 350)
    code(c, 'Фактические ответы Java REST API', lines('api-smoke.log', 'hello|horrible|meeting|отлично|blank|oversized|PASS', 8), 432, y, 472, 11)
    c.showPage()

    y = slide_head(c, 5, 'Сборка и развёртывание', 'Maven собирает JAR. В финальный Alpine-образ попадает только приложение и runtime jlink.')
    y = code(c, 'Диагностика сборки и образа', lines('maven.log', 'BUILD SUCCESS', 1) + '\n' + (lines('image-size.log', None, 4) or 'Фактический размер образа не подтверждён.'), 56, y, 848, 12)
    code(c, 'Диагностика Minikube / kubectl', lines('cluster.log', 'NAME|Ready|VERSION', 6) or lines('minikube-retry.log', 'Using|StartHost failed|VT-X', 5), 56, y, 848, 11.5)
    c.showPage()

    y = slide_head(c, 6, 'Нагрузка и масштабирование', 'HPA нацелен на 60% от запроса CPU. Допустимый диапазон составляет 3–8 реплик.')
    y1 = column(c, '3 → 7 → 8 → 3 реплики', 'В журналах Fortio зафиксирован 281 241 ответ HTTP 200 после прогрева. После снижения CPU сервис вернулся к трём готовым подам.', 56, y, 350)
    column(c, 'По 5 запросов на под', 'При трёх исходных репликах зафиксировано равномерное распределение 15 запросов через Ingress.', 56, y1, 350)
    image(c, 'hpa.jpg', 430, y, 474, 275, trim=0.52)
    c.showPage()

    y = slide_head(c, 7, 'Prometheus и Grafana', 'ServiceMonitor опрашивает /actuator/prometheus каждые 15 секунд.')
    if (EVIDENCE / 'grafana.jpg').exists():
        image(c, 'grafana.jpg', 56, y, 848, 323, trim=0.75)
    else:
        y1 = column(c, 'Панели', 'Запросы в секунду, p95, CPU по подам, реплики HPA, предсказания по классам и число доступных целей.', 56, y, 350)
        column(c, 'Сбор данных', stage(monitoring_up, 'Prometheus опросил цели. Результат сохранён в журнале.', 'Локальный Actuator отдаёт счётчики. Опрос подов в кластере не подтверждён.'), 56, y1, 350)
        code(c, 'Фактический вывод', lines('monitoring.log', 'PASS|up=|Running', 8) or lines('api-smoke.log', 'sentiment_predictions|PASS', 4), 430, y, 474, 10.6)
    c.showPage()

    y = slide_head(c, 8, 'Бессерверный ИИ и локальность', 'При запуске LLM важны время загрузки весов и повторное использование вычислений.')
    for x, title, body, ref in [
        (56, 'ServerlessLLM', 'Хранит контрольные точки рядом с GPU и учитывает время загрузки при размещении модели.', PAPERS[0]),
        (349, 'ServerlessLoRA', 'Переиспользует базовые веса и заранее загружает артефакты адаптеров.', PAPERS[1]),
        (642, 'Preble', 'Использует общие префиксы для повторного применения KV-кэша и учитывает очереди.', PAPERS[4]),
    ]:
        end = column(c, title, body, x, y, 255)
        text(c, link('arXiv:' + ref[3], 'https://arxiv.org/abs/' + ref[3]), x, end + 4, 255, 12)
    text(c, 'Для проекта можно отдельно измерить запуск JVM, готовность пода и первый успешный запрос.', 56, 125, 848, 17.4, 24)
    c.showPage()

    y = slide_head(c, 9, 'Управление ресурсами и RL', 'Выбор сигнала зависит от того, чем управляет контроллер: количеством подов, узлом или заданием.')
    for x, title, body, ref in [
        (56, 'SLO Autoscaling', 'Совмещает прикладные метрики, условия размещения и ограничения стоимости.', PAPERS[2]),
        (349, 'SchedMate', 'Оценивает GPU-задачи по коду, логам и истории, дополняя существующий планировщик.', PAPERS[3]),
        (642, 'SDQN / SDQN-n', 'Применяет DQN к выбору узлов и проверяет эффект консолидации вычислительных подов.', PAPERS[5]),
    ]:
        end = column(c, title, body, x, y, 255)
        text(c, link('arXiv:' + ref[3], 'https://arxiv.org/abs/' + ref[3]), x, end + 4, 255, 12)
    text(c, 'Базовый опыт для проекта — сравнение CPU-HPA и политики по очереди или p95 на одинаковой трассе.', 56, 125, 848, 17.4, 24)
    c.showPage()

    y = slide_head(c, 10, 'Итоги', 'Учебный сервис объединяет локальную модель, декларативное развёртывание и метрики.')
    y1 = column(c, 'Подтверждено', 'JAR, три класса тональности, HTTP 400 и выдача метрик.' + stage(image_pass, ' Размер образа соответствует заданию.', '') + stage(scaled and scaled_down, ' Проверен цикл HPA 3 → 8 → 3.', ''), 56, y)
    column(c, 'Проблемы стенда', 'VirtualBox запустился после обхода проверки VT-x. Для внешних IP использовалось решение MetalLB в сети VirtualBox host-only.', 56, y1)
    y2 = column(c, 'Результат Kubernetes', stage(routes_up and monitoring_up, 'Проверены Ingress, реплики и мониторинг.', 'Готовность ресурсов и мониторинг следует сверять с фактическими журналами. Подготовлены YAML и дашборд.'), 503, y)
    column(c, 'Перспектива', 'Добавить внешний корпус оценки модели и провести повторяемый эксперимент по p95 и реплика-минутам.', 503, y2)
    c.showPage()
    c.save()
    writer = writer_with_metadata(path)
    with path.open('wb') as destination:
        writer.write(destination)


if __name__ == '__main__':
    make_report()
    make_deck()
