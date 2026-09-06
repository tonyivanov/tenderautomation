"""Constants for Scoring v2 — service actions, IT objects, strong markers."""
from __future__ import annotations

from typing import Any

# ── Service Actions (что GIS потенциально может делать) ──────────────────
SERVICE_ACTIONS: list[str] = [
    "аудит",
    "обследование",
    "анализ",
    "экспертиза",
    "тестирование",
    "пентест",
    "проектирование",
    "разработка архитектуры",
    "внедрение",
    "развертывание",
    "развёртывание",
    "настройка",
    "администрирование",
    "поддержка",
    "сопровождение",
    "обслуживание",
    "модернизация",
    "реконструкция",
    "миграция",
    "перевод",
    "оптимизация",
    "защита",
    "мониторинг",
    "реагирование",
    "резервное копирование",
    "восстановление",
    "аутсорсинг",
    "консалтинг",
    "построение",
    "развитие",
    "обеспечение отказоустойчивости",
]

# ── IT Objects (объекты, системы, технологии) ────────────────────────────
IT_OBJECTS: list[str] = [
    "it инфраструктура",
    "информационная инфраструктура",
    "сервер",
    "серверная операционная система",
    "linux",
    "windows server",
    "сеть",
    "сетевая инфраструктура",
    "сетевое оборудование",
    "виртуализация",
    "виртуальная среда",
    "vmware",
    "hyper v",
    "hyper-v",
    "proxmox",
    "kubernetes",
    "openshift",
    "docker",
    "система хранения данных",
    "схд",
    "ceph",
    "netapp",
    "резервное копирование",
    "netbackup",
    "veeam",
    "ленточная библиотека",
    "цод",
    "база данных",
    "субд",
    "postgresql",
    "ms sql",
    "oracle",
    "active directory",
    "exchange",
    "waf",
    "pam",
    "ngfw",
    "ddos",
    "информационная безопасность",
    "защищенность",
    "защищённость",
    "периметр",
    "ci cd",
    "ci/cd",
    "devops",
    "devsecops",
    "kafka",
    "zabbix",
    "grafana",
    "программно аппаратный комплекс",
    "программно-аппаратный комплекс",
    "инфраструктурное по",
]

# ── Strong Profile Markers (правила из ТЗ) ───────────────────────────────
STRONG_RULES: list[dict[str, Any]] = [
    # DevOps
    {"id": "devops", "phrases": ["devops", "devsecops"], "weight": 25},
    # Kubernetes / OpenShift / Docker
    {"id": "kubernetes", "phrases": ["kubernetes", "openshift", "docker", "среда контейнеризации", "контейнерная платформа"], "weight": 25},
    # CI/CD
    {"id": "ci_cd", "phrases": ["ci/cd", "ci cd"], "weight": 20},
    # Linux & Server Admin
    {"id": "linux_admin", "phrases": ["администрирование linux", "администрирование сервер", "системное администрирование"], "weight": 15},
    # Virtualization
    {"id": "virtualization", "phrases": ["виртуализация", "vmware", "vsphere", "vcenter", "hyper-v", "hyper v", "proxmox"], "weight": 18},
    # Cloud
    {"id": "cloud_infra", "phrases": ["облачная инфраструктура"], "weight": 15},
    # Managed IT Infrastructure
    {"id": "managed_it_infra", "phrases": ["поддержка it инфраструктуры", "сопровождение it инфраструктуры", "обслуживание it инфраструктуры"], "weight": 15},
    # IT Audit
    {"id": "it_audit", "phrases": ["аудит it инфраструктуры", "аудит ит инфраструктуры", "обследование it инфраструктуры", "аудит текущего состояния"], "weight": 25},
    # Pentest
    {"id": "pentest", "phrases": ["пентест", "тестирование на проникновение"], "weight": 20},
    # Security Analysis
    {"id": "security_analysis", "phrases": ["анализ защищ", "анализ информационной безопасности", "кибербезопасност"], "weight": 20},
    # Servers, Networks, Storage
    {"id": "server_network_storage", "phrases": ["серверная инфраструктура", "сетевая инфраструктура", "схд", "система хранения данных", "серверное оборудование"], "weight": 12},
    # Ceph
    {"id": "ceph", "phrases": ["ceph"], "weight": 20},
    # VMware / Veeam / NetBackup
    {"id": "vmware_veeam", "phrases": ["vmware", "veeam", "netbackup"], "weight": 18},
    # Backup
    {"id": "backup", "phrases": ["резервное копирование", "система резервного копирования", "ленточная библиотека", "ленточное хранилище"], "weight": 15},
    # Migration & Modernization
    {"id": "migration_modernization", "phrases": ["миграция инфраструктуры", "миграция серверов", "миграция в облако", "модернизация it инфраструктуры", "модернизация ит инфраструктуры"], "weight": 18},
    # Import Substitution
    {"id": "import_substitution", "phrases": ["импортозамещение"], "weight": 18},
    # IT Outsourcing
    {"id": "it_outsource", "phrases": ["аутсорсинг системного администрирования", "аутсорсинг it"], "weight": 17},
    # Monitoring
    {"id": "monitoring", "phrases": ["zabbix", "prometheus", "мониторинг it инфраструктуры"], "weight": 15},
    # Databases
    {"id": "databases", "phrases": ["postgresql", "postgres pro", "clickhouse", "greenplum"], "weight": 12},
    # Astra Linux
    {"id": "astra_linux", "phrases": ["astra linux"], "weight": 12},
    # DLP
    {"id": "dlp", "phrases": ["dlp", "dlp система", "dlp систем"], "weight": 14},
    # KII (critical information infrastructure)
    {"id": "kii", "phrases": ["кии", "категорирование", "критическая информационная инфраструктура"], "weight": 16},
    # Container security
    {"id": "container_protection", "phrases": ["защита контейнер", "защита среды контейнеризации", "безопасность контейнер"], "weight": 16},
    # Network architecture expertise
    {"id": "network_architecture_expertise", "phrases": ["архитектура сети", "экспертиза архитектуры сети", "независимая техническая экспертиза"], "weight": 15},
    # IT infrastructure reconstruction
    {"id": "it_reconstruction", "phrases": ["реконструкция it инфраструктуры", "реконструкция ит инфраструктуры"], "weight": 16},
    # Security assessment (practical)
    {"id": "practical_security", "phrases": ["практический анализ защищ", "анализ защищ"], "weight": 20},
    # Oracle migration
    {"id": "oracle_migration", "phrases": ["oracle db migration", "миграция oracle", "oracle на postgresql"], "weight": 14},
    # Cloud + virtual servers
    {"id": "cloud_virtual", "phrases": ["облачная инфраструктура", "виртуальных серверов", "iaas"], "weight": 15},
    # Monitoring IT infrastructure deployment
    {"id": "monitoring_deployment", "phrases": ["внедрение мониторинга", "внедрение системы мониторинга", "мониторинг it инфраструктуры"], "weight": 15},
    # Web security testing
    {"id": "web_security", "phrases": ["анализ защищ.{0,20}(сайт|приложен|веб)"], "weight": 14},
]

# ── Safe Hard-Stop Phrases (точные, не широкие) ──────────────────────────
SAFE_HARD_STOP_PHRASES: list[dict[str, Any]] = [
    {"id": "cleaning", "phrases": ["клининг", "комплексная уборка", "уборка помещений", "уборка офисных помещений"], "confidence": 0.99},
    {"id": "catering", "phrases": ["комплексное питание", "доставка обедов", "горячее питание", "организация питания"], "confidence": 0.99},
    {"id": "transportation", "phrases": ["пассажирские перевозки", "грузовые перевозки", "перевозка пассажиров", "транспортные услуги по перевозке"], "confidence": 0.99},
    {"id": "financial_audit", "phrases": ["бухгалтерский аудит", "финансовый аудит", "аудит бухгалтерской отчётности", "аудит бухгалтерского учёта"], "confidence": 0.99},
    {"id": "labor_conditions", "phrases": ["специальная оценка условий труда", "оценка условий труда", "соут"], "confidence": 0.99},
    {"id": "building_repair", "phrases": ["ремонт помещений", "эксплуатация здания", "техническое обслуживание здания", "инженерные сети здания"], "confidence": 0.99},
    {"id": "pr_smm", "phrases": ["pr продвижение", "рекламная кампания", "smm сопровождение", "ведение социальных сетей", "пиар поддержка", "btl"], "confidence": 0.99},
    {"id": "website", "phrases": ["создание сайта", "разработка сайта", "поддержка сайта", "продвижение сайта", "сопровождение сайта", "доработка сайта"], "confidence": 0.99},
    {"id": "1c", "phrases": ["1с сопровождение", "1с доработка", "поддержка 1с", "разработка 1с", "1с зуп", "1с ут", "1с erp"], "confidence": 0.99},
    {"id": "office_equipment", "phrases": ["офисная техника", "оргтехника", "мфу", "принтеры", "картриджи", "ккт", "контрольно-кассовая техника"], "confidence": 0.99},
    {"id": "legal", "phrases": ["юридическое сопровождение", "юридические услуги"], "confidence": 0.99},
    {"id": "medical", "phrases": ["медицинские услуги", "медицинские осмотры", "предрейсовые осмотры"], "confidence": 0.99},
    {"id": "environmental", "phrases": ["экологическое сопровождение"], "confidence": 0.99},
]

# ── Manual Safety Net (инварианты после всех стадий) ────────────────────
# Эти слова гарантируют candidate=True независимо от остальных решений
MANUAL_SAFETY_NET: list[str] = [
    "пентест",
    "тестирование на проникновение",
]
