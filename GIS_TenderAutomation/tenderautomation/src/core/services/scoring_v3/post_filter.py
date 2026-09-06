"""v3.2.2 — Deterministic post-filter layer after LLM classification.

Applies business invariants that LLM sometimes misses:
- Force reject for known non-target products/objects
- Force reject for pure supply/license without substantive service
- Force min P2 for known infrastructure objects (false negative protection)
- Retail object maintenance detection
"""
from __future__ import annotations

import logging

from . import models

logger = logging.getLogger(__name__)

# ── Known non-target products (lowercase for matching) ────────────────
NON_TARGET_PRODUCTS = {
    "1с", "1с:", "directum", "консультантплюс", "consultantplus",
    "bpm", "ibm planning", "планирование ibm", "техэксперт",
}

# ── Known non-target physical objects ─────────────────────────────────
NON_TARGET_OBJECTS = {
    "ккт", "контрольно-кассов", "касса", "кассов",
    "преобразователь частоты", "частотный преобразователь",
    "холодоснабж", "клапан", "кондиционер", "вентиляц",
    "громкоговорящ", "громкой связи", "ггс",
    "промышленное оборудование", "технологическое оборудование",
}

# ── Retail/object maintenance patterns ────────────────────────────────
RETAIL_MAINTENANCE = {
    "монетка", "обслуживание объектов", "обслуживанию объектов",
    "розничн", "торговых объектов",
}

# ── False negative protection: known infrastructure objects ───────────
INFRA_POSITIVE = {
    "wi-fi", "аудит wi-fi", "радиообследование", "беспроводная сеть",
    "dpi", "allot", "dpi allot",
    "ленточн библиотек", "ленточные библиотеки",
    "hpe msa", "hpe 3par", "netapp", "ceph",
    "модернизац резервного копирования", "поддержка программно-аппаратного",
    "настройка средств защиты", "средств защиты информации",
    "скс", "структурированных кабельных",
}

# ── Additional non-target objects (v3.2.3) ────────────────────────────
NON_TARGET_OBJECTS_V323 = {
    "инженерных систем", "инженерные системы", "складского комплекса",
    "avid", "orad", "преобразовател", "частот", "плавного пуска",
    "технологическое оборудование", "технологического оборудования",
    "панель управления", "рабочая документация", "разработка по",
    "торговых точек", "торговые точки", "оборудование ито",
}


def _title_lower(title: str) -> str:
    return title.lower().strip()


def apply_post_filter(
    result: models.V3Result,
    title: str,
) -> models.V3Result:
    """Apply business invariants to a single tender result.

    Returns modified V3Result.
    """
    if not result or not result.first_pass:
        return result

    fp = result.first_pass
    title_low = _title_lower(title)
    domain = str(fp.primary_domain).lower()
    proc_type = str(fp.procurement_type).lower()
    verdict = str(result.final_verdict).lower()
    queue = result.queue

    # ── 1. Force reject: known non-target products ────────────────────
    for product in NON_TARGET_PRODUCTS:
        if product in title_low:
            # v3.2.3.5: 1С with infra context → minimum P2
            if "1с" in product and _has_1c_infrastructure_context(title_low):
                logger.debug(f"post_filter: 1C infra exception: {title[:80]}")
                result.final_verdict = "review"
                result.final_fit_score = 45
                result.final_confidence = 0.60
                result.queue = "P2"
                result.priority = 45
                result.analysis_status = "post_filter_1c_exception"
                return result
            logger.debug(f"post_filter: force_reject (product={product}): {title[:80]}")
            result.final_verdict = "reject"
            result.final_fit_score = 0
            result.final_confidence = 0.95
            result.queue = "reject"
            result.priority = 0
            result.analysis_status = "post_filter_reject"
            return result

    # ── 2. Force reject: known non-target physical objects ────────────
    for obj in NON_TARGET_OBJECTS:
        if obj in title_low:
            logger.debug(f"post_filter: force_reject (object={obj}): {title[:80]}")
            result.final_verdict = "reject"
            result.final_fit_score = 0
            result.final_confidence = 0.95
            result.queue = "reject"
            result.priority = 0
            result.analysis_status = "post_filter_reject"
            return result

    # ── 3. Force reject: retail/object maintenance without IT object ──
    has_retail = any(p in title_low for p in RETAIL_MAINTENANCE)
    has_infra = any(p in title_low for p in INFRA_POSITIVE)
    has_it_object = _has_it_object(title_low)
    if has_retail and not has_infra and not has_it_object:
        logger.debug(f"post_filter: force_reject (retail_maint): {title[:80]}")
        result.final_verdict = "reject"
        result.final_fit_score = 0
        result.final_confidence = 0.95
        result.queue = "reject"
        result.priority = 0
        result.analysis_status = "post_filter_reject"
        return result

    # ── 3.5 (v3.2.3): Force reject for additional non-target objects ──
    for obj in NON_TARGET_OBJECTS_V323:
        if obj in title_low:
            logger.debug(f"post_filter: force_reject (v323_object={obj}): {title[:80]}")
            result.final_verdict = "reject"
            result.final_fit_score = 0
            result.final_confidence = 0.95
            result.queue = "reject"
            result.priority = 0
            result.analysis_status = "post_filter_reject"
            return result

    # ── 3.6 (v3.2.3.2): Fix procurement_type BEFORE supply check ──────
    result = _fix_procurement_type(result, title_low)
    fp = result.first_pass
    proc_type = str(fp.procurement_type).lower() if fp else "unknown"

    # ── 4. Force reject: pure supply/license without substantive service
    if proc_type in {"supply_only", "licenses_only"} and not _has_substantive_service(title_low):
        logger.debug(f"post_filter: force_reject (pure_{proc_type}): {title[:80]}")
        result.final_verdict = "reject"
        result.final_fit_score = 0
        result.final_confidence = 0.95
        result.queue = "reject"
        result.priority = 0
        result.analysis_status = "post_filter_reject"
        return result

    # ── 5. Force min P2: known infrastructure objects ─────────────────
    for pos in INFRA_POSITIVE:
        if pos in title_low and verdict == "reject":
            logger.debug(f"post_filter: force_P2 (infra_positive={pos}): {title[:80]}")
            result.final_verdict = "review"
            result.final_fit_score = 50
            result.final_confidence = 0.60
            result.queue = "P2"
            result.priority = 50
            result.analysis_status = "post_filter_force_p2"
            return result

    return result


def _has_it_object(title_low: str) -> bool:
    """Check if title contains any explicit IT infrastructure objects."""
    it_objects = {
        "сервер", "схд", "сеть", "cisco", "juniper", "hpe", "dell",
        "netapp", "vmware", "oracle", "баз данных", "мониторинг",
        "виртуализац", "облак", "kubernetes", "docker", "devops",
        "ci/cd", "резервн", "сетевое оборуд", "маршрутизатор",
        "коммутатор", "межсетев", "инфраструктур",
    }
    return any(obj in title_low for obj in it_objects)


def _fix_procurement_type(result: models.V3Result, title_low: str) -> models.V3Result:
    """Fix LLM misclassification of procurement_type using regex stems.

    Must be called BEFORE force_reject rules so mixed→P2 applies correctly.
    """
    import re

    fp = result.first_pass
    if not fp:
        return result

    # «Поставка услуг» ≠ поставка товаров
    if "поставка услуг" in title_low:
        return result

    # Regex stems match Russian word forms: поставк* = поставка/поставки/поставке/поставку/поставкой
    goods_patterns = [
        r"\bпоставк\w*", r"\bзакупк\w+\s+оборудован\w*",
        r"\bприобретен\w+\s+оборудован\w*", r"\bпредоставлен\w+\s+прав\w*",
    ]
    service_patterns = [
        r"\bвнедрен\w*", r"\bнастро\w*", r"\bмиграц\w*", r"\bмодернизац\w*",
        r"\bадминистр\w*", r"\bсопровожд\w*", r"\bподдержк\w*",
        r"\bпусконалад\w*", r"\bразвертыван\w*", r"\bаудит\w*",
        r"\bпроектирован\w*", r"\bобследован\w*", r"\bустановк\w*",
        r"\bинтеграц\w*",
    ]

    has_goods = any(re.search(p, title_low) for p in goods_patterns)
    has_service = any(re.search(p, title_low) for p in service_patterns)

    if has_goods and has_service:
        fp.procurement_type = "mixed"
        # v3.2.3.6: Mixed IT procurement → P2, not Reject
        domain = str(fp.primary_domain).lower()
        if domain not in {"non_it", "facilities", "web_and_marketing", "office_it", "supply", "unknown"}:
            result.final_verdict = "review"
            result.final_fit_score = 50
            result.final_confidence = 0.65
            result.queue = "P2"
            result.priority = 55
            result.analysis_status = "procurement_type_mixed_restore"
            return result
    elif has_goods:
        fp.procurement_type = "supply_only"
    elif has_service:
        fp.procurement_type = "services"

    return result


def _has_1c_infrastructure_context(title_low: str) -> bool:
    """1C with infrastructure context (Astra Linux, PostgreSQL, migration) → not reject."""
    return any(w in title_low for w in {
        "astra linux", "linux", "postgresql", "субд",
        "миграция инфраструктуры", "перевод инфраструктуры",
        "серверы 1с", "кластер 1с",
    })


def _has_substantive_service(title_low: str) -> bool:
    """Check if title mentions substantive service beyond standard warranty."""
    service_words = {
        "внедрение", "настройка", "миграция", "модернизация",
        "администрирование", "сопровождение", "аудит", "проектирование",
        "обследование", "установка", "интеграция",
        "техническая поддержка", "техническое сопровождение",
        "пусконаладочные работы", "развертывание",
    }
    # Pure supply/license WITH substantive service → not rejected
    return any(w in title_low for w in service_words)