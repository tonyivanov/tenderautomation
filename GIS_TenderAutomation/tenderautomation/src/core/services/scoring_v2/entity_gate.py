"""Stage 2.5: Entity Candidate Gate (v2.4 — независимые детекторы действий, объектов, контекста)."""
from __future__ import annotations

import re

from .models import ClassifierDecision

ENTITY_ACTIONS: dict[str, str] = {
    "аудит": "audit", "аудитор": "audit",
    "анализ": "analysis", "проанализировать": "analysis",
    "оценк": "assessment", "обследован": "survey",
    "исследован.{0,10}состоян": "assessment",
    "модернизац": "modernization", "реконструкц": "reconstruction",
    "апгрейд": "modernization", "обновлен.{0,10}инфраструктур": "modernization",
    "миграц": "migration", "перенос": "migration", "переход": "migration", "перевод": "migration",
    "внедрен": "implementation", "развертыван": "implementation",
    "развёртыван": "implementation", "установк": "implementation",
    "настройк": "implementation", "запуск": "implementation",
    "поддержк": "support", "техническ.{0,10}поддержк": "support",
    "сопровожден": "support", "обслуживан": "support", "сервисн.{0,10}обслуживан": "support",
    "администрирован": "administration", "эксплуатац": "administration", "управлен": "administration",
    "проектирован": "design", "разработк.{0,10}архитектур": "design",
    "техническ.{0,10}экспертиз": "design", "разработк.{0,10}подход": "design",
    "защит": "security", "анализ.{0,5}защищен": "security",
    "тестирован.{0,10}на.{0,10}проникновен": "security", "пентест": "security",
    "категорирован": "security", "мониторинг.{0,10}событ.{0,10}безопасност": "security",
    "аутсорсинг": "outsourcing", "предоставлен.{0,10}специалист": "outsourcing",
    "выполнен.{0,10}работ.{0,10}(специалист|подрядчик)": "outsourcing",
    "предоставлен": "provisioning", "аренд": "provisioning",
    "размещен": "provisioning", "колокейшн": "provisioning", "colocation": "provisioning",
    "услуг": "service", "работ": "service",
}

ENTITY_OBJECTS: dict[str, str] = {
    "it.{0,5}(инфраструктур|ландшафт|контур)": "it_infrastructure",
    "информационн.{0,10}инфраструктур": "it_infrastructure",
    "инфраструктурн.{0,10}по": "infra_software",
    "программно.{0,5}аппаратн.{0,10}комплекс": "pak",
    "сервер": "server",
    "вычислительн.{0,10}(ресурс|мощност)": "compute_resources",
    "виртуальн.{0,10}(вычислительн|мощност)": "compute_resources",
    "iaas": "cloud", "облачн.{0,10}(инфраструктур|ресурс|сервис)": "cloud",
    "выделен.{0,10}сервер": "dedicated_server",
    "виртуализац": "virtualization", "виртуальн.{0,10}сред": "virtualization",
    "vmware": "virtualization", "hyper.{0,5}v": "virtualization", "proxmox": "virtualization",
    "kubernetes": "containers", "openshift": "containers", "docker": "containers",
    "контейнеризац": "containers",
    "сетев.{0,10}(инфраструктур|оборудован)": "network_infrastructure",
    "архитектур.{0,10}сет": "network_architecture",
    "локальн.{0,10}вычислительн.{0,10}сет": "network_infrastructure",
    "маршрутизатор": "network_equipment", "коммутатор": "network_equipment",
    "cisco": "network_equipment", "juniper": "network_equipment",
    "lan": "network_equipment", "wan": "network_equipment",
    "wi.{0,5}fi": "network_equipment", "роутер": "network_equipment",
    "систем.{0,10}хранен": "storage", "схд": "storage",
    "netapp": "storage", "dell.{0,10}storage": "storage",
    "ленточн.{0,10}(библиотек|хранилищ)": "tape_library",
    "резервн.{0,10}копирован": "backup", "netbackup": "backup", "veeam": "backup",
    "баз.{0,10}данн": "database", "субд": "database",
    "postgresql": "database", "ms.{0,5}sql": "database",
    "oracle.{0,10}(database|db)": "database", "mysql": "database",
    "центр.{0,10}обработк.{0,10}данн": "data_center", "цод": "data_center",
    "размещен.{0,10}оборудован": "data_center", "аренд.{0,10}мощност": "data_center",
    "колокейшн": "data_center", "стойко.{0,5}мест": "data_center",
    "информационн.{0,10}безопасност": "infosec",
    "анализ.{0,5}защищен": "security_assessment", "пентест": "pentest",
    "кии": "kii", "waf": "infosec", "pam": "infosec", "dlp": "infosec",
    "ngfw": "infosec", "ddos": "infosec", "анти.{0,5}ddos": "infosec",
    "систем.{0,10}защит": "security_tools",
    "защит.{0,10}(контейнер|сред.{0,10}контейнеризац)": "container_security",
    "llm": "llm", "kafka": "middleware", "zabbix": "monitoring",
    "grafana": "monitoring", "prometheus": "monitoring", "devops": "devops",
}

IT_CONTEXT_WORDS = [
    "it", "информационный", "сервер", "программный", "вычислительный",
    "цифровой", "субд", "цод", "cloud", "облачный", "virtual", "виртуальный",
    "cisco", "vmware", "linux", "oracle", "kubernetes", "схд", "backup",
    "сетевой", "сетевого", "маршрутизатор", "коммутатор", "роутер",
]

NON_IT_NEGATIVE_CONTEXTS = [
    "инженерные сети", "инженерных сетей", "инженерным сетям",
    "тепловые сети", "тепловых сетей", "водопроводные сети",
    "канализационные сети", "электрические сети", "газовые сети",
    "дорожная сеть", "железнодорожная инфраструктура",
    "инженерная инфраструктура здания", "строительная инфраструктура",
    "лифтовое оборудование", "вентиляция", "кондиционирование",
    "электроснабжение", "противопожарные системы",
    "слаботочные системы здания", "авторский надзор",
    "инженерных систем", "инженерные системы здания",
]


def detect_entity_actions(text: str) -> set[str]:
    found: set[str] = set()
    for stem, name in ENTITY_ACTIONS.items():
        if re.search(stem, text):
            found.add(name)
    return found


def detect_entity_it_objects(text: str) -> set[str]:
    found: set[str] = set()
    for stem, name in ENTITY_OBJECTS.items():
        if re.search(stem, text):
            found.add(name)
    return found


def detect_it_context(text: str, objects: set[str]) -> bool:
    if objects:
        return True
    return any(w in text for w in IT_CONTEXT_WORDS)


def detect_negative_contexts(text: str) -> bool:
    return any(ctx in text for ctx in NON_IT_NEGATIVE_CONTEXTS)


def has_strong_it_object(objects: set[str]) -> bool:
    strong_set = {"data_center", "cloud", "compute_resources", "server",
                  "storage", "backup", "network_architecture", "network_infrastructure",
                  "containers", "database"}
    return bool(objects & strong_set)


def apply_entity_gate(normalized_text: str) -> ClassifierDecision:
    actions = detect_entity_actions(normalized_text)
    objects = detect_entity_it_objects(normalized_text)
    it_context = detect_it_context(normalized_text, objects)
    negative = detect_negative_contexts(normalized_text)

    if negative and not has_strong_it_object(objects):
        return ClassifierDecision(candidate=False, confidence=0.0,
                                  reason="negative_context_blocked",
                                  detail={"all_actions": list(actions), "all_objects": list(objects),
                                          "it_context": it_context, "negative_context": True})

    if actions and objects and it_context:
        return ClassifierDecision(candidate=True, confidence=0.85, reason="entity_gate",
                                  detail={"all_actions": list(actions), "all_objects": list(objects),
                                          "it_context": True, "negative_context": negative})

    return ClassifierDecision(candidate=False, confidence=0.0, reason="no_entity_match",
                              detail={"all_actions": list(actions), "all_objects": list(objects),
                                      "it_context": it_context, "negative_context": negative})