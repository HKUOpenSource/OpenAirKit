import copy
from datetime import datetime, timezone
import math

SCHEMA_VERSION = 4
QUALITY_STATES = frozenset({'ok', 'stale', 'unavailable', 'unsupported'})


def utc():
    return datetime.now(timezone.utc).isoformat()


def observation(source, entity, name, value=None, unit="state", status="ok", reason=None, window=None):
    if isinstance(value, float) and not math.isfinite(value):
        value, status, reason = None, "unavailable", "non_finite_sample"
    if status not in QUALITY_STATES:
        raise ValueError('invalid_observation_quality')
    if status != 'ok' and not reason:
        reason = {'stale': 'sample_expired', 'unavailable': 'sample_unavailable',
                  'unsupported': 'source_does_not_provide_metric'}[status]
    return dict(source=source, entity=entity, name=name, value=value, unit=unit,
                status=status, reason=reason, observed_at=utc(), window_seconds=window)


def age_seconds(timestamp, now=None):
    try:
        return ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(timestamp)).total_seconds()
    except (ValueError, TypeError):
        return math.inf


def service_health(service):
    if not service or service.get('status', 'ok') != 'ok':
        return 'unknown'
    if service.get('state') in (None, 'unknown', 'stale'):
        return 'unknown'
    if service.get('state') not in ('running', 'active'):
        return 'failed' if service.get('state') in ('exited', 'dead', 'failed') else 'degraded'
    return {'healthy': 'healthy', 'unhealthy': 'failed', 'starting': 'degraded'}.get(service.get('health'), 'unknown')


def infrastructure_health(result):
    values = {(m['entity'], m['name']): m for m in result['observations']}
    def metric(entity, name):
        item = values.get((entity, name), {})
        return item.get('value') if item.get('status') == 'ok' else None
    host, reasons = 'healthy', []
    for resource in ('memory', 'disk'):
        used, total = metric('spark', resource + '_used'), metric('spark', resource + '_total')
        if not isinstance(used, (int, float)) or not isinstance(total, (int, float)) or total <= 0:
            reasons.append(resource + '_evidence_unavailable')
            if host == 'healthy':
                host = 'unknown'
        elif used / total >= .9:
            reasons.append(resource + '_pressure')
            if host != 'failed':
                host = 'failed' if used / total >= .97 else 'degraded'
    for c in result.get('components', []):
        if c['id'] == 'spark':
            c.update(state=host, health=host, health_reasons=reasons)
            c.setdefault('details', {})['health_reason'] = ', '.join(reasons) if reasons else 'resource_thresholds_normal'
        elif c.get('kind') == 'nf':
            c['business_health'] = service_health(c)
    count, holders = metric('spark', 'b210_devices'), metric('spark', 'b210_holder_pids')
    b210 = 'unknown' if count is None else 'healthy' if count == 1 else 'failed'
    if isinstance(holders, list) and len(holders) > 1:
        b210 = 'failed'
    speed = metric('spark', 'b210_speed')
    try:
        if b210 == 'healthy' and float(speed) < 5000:
            b210 = 'degraded'
    except (ValueError, TypeError):
        if b210 == 'healthy':
            b210 = 'unknown'
    return host, b210, metric


def fresh_snapshot(snapshot, ttl=20):
    result = copy.deepcopy(snapshot)
    age = age_seconds(result["observed_at"])
    result["collector_status"] = ("ok" if -5 <= age <= ttl else "stale") if result.get('collector_status') != 'unavailable' else 'unavailable'
    if result["collector_status"] != "ok":
        result["last_active_stack"] = result.get("active_stack", "unknown")
        result["active_stack"] = "unknown"
        for service in result.get("services", []):
            service["status"] = "stale"
            service["state"] = "stale"
            service["health"] = "stale"
    for item in result["observations"]:
        if item["status"] == "ok" and not -5 <= age_seconds(item["observed_at"]) <= ttl:
            item.update(status="stale", reason="sample_expired")
    for component in result.get("components", []) + result.get("links", []):
        if result["collector_status"] != "ok":
            component.update(state="unknown", status="stale")
        for metric in component.get("metrics", []):
            if metric["status"] == "ok" and not -5 <= age_seconds(metric["observed_at"]) <= ttl:
                metric.update(status="stale", reason="sample_expired")
    for device in result.get("devices", []):
        expiry = ttl if device["source"] == "ocudu_scheduler" else 90
        if result["collector_status"] != "ok" or device["stack"] != result["active_stack"] or not -5 <= age_seconds(device["observed_at"]) <= expiry:
            device['last_registration'] = device.get('last_registration', device.get('registration', 'unknown'))
            device['registration'] = 'unknown'
            device.update(status="stale", state="unknown")
        for metric in device.get("metrics", []):
            if metric["status"] == "ok" and not -5 <= age_seconds(metric["observed_at"]) <= ttl:
                metric.update(status="stale", reason="sample_expired")
        for session in device.get("sessions", []):
            if device.get("status") != "ok" or device.get('registration') == 'deregistered' or not -5 <= age_seconds(session["observed_at"]) <= 90:
                session["status"] = "stale"
        from .connectivity import connection_state
        connection_state(device)
    # Recompute report counts after per-session expiry, including Web reads of cached snapshots.
    for item in result['observations']:
        if item['name'] in ('reported_pdu_count', 'historical_pdu_count'):
            stack, dnn = item['entity'].split(':', 1)
            reports = [s for d in result.get('devices', []) if d['stack'] == stack for s in d.get('sessions', []) if s['dnn'] == dnn]
            current = [s for s in reports if s['status'] == 'ok']
            historical = item['name'] == 'historical_pdu_count'
            item['value'] = len(reports) - len(current) if historical else len(current)
            item['status'] = 'stale' if result['collector_status'] != 'ok' or (reports and not current and not historical) else item['status']
    result["health"] = {}
    host, b210, metric = infrastructure_health(result)
    for stack in ("ocudu",):
        services = [s for s in result.get("services", []) if s["stack"] == stack]
        ran = next((v for v in result["observations"] if v["entity"] == stack and v["name"] == "n2_associated"), None)
        def healthy(roles):
            selected = [s for s in services if s["role"] in roles]
            if result["collector_status"] != "ok" or len(selected) != len(roles):
                return "unknown"
            states = [service_health(s) for s in selected]
            return next((s for s in ('failed', 'degraded', 'unknown') if s in states), 'healthy')
        process = metric(stack, 'radio_process')
        pid = metric(stack, 'radio_pid')
        holders = metric('spark', 'b210_holder_pids')
        ran_health = 'unknown'
        reason = 'radio_evidence_unavailable'
        if result['collector_status'] == 'ok':
            if process == 'failed':
                ran_health, reason = 'failed', 'radio_process_failed'
            elif process == 'inactive':
                ran_health, reason = 'inactive', 'radio_inactive'
            elif process == 'active':
                if b210 == 'failed':
                    ran_health, reason = 'failed', 'radio_hardware_fault'
                elif ran and ran['status'] == 'ok' and ran['value'] is False:
                    ran_health, reason = 'degraded', 'n2_not_associated'
                elif isinstance(holders, list) and holders != [pid]:
                    ran_health, reason = 'degraded', 'radio_usb_owner_mismatch'
                elif b210 == 'degraded':
                    ran_health, reason = 'degraded', 'usb_speed_below_usb3'
                elif ran and ran['status'] == 'ok' and ran['value'] is True and b210 == 'healthy' and holders == [pid]:
                    ran_health, reason = 'healthy', 'process_usb_owner_and_n2_verified'
                if any((metric(stack, 'log_' + name) or 0) > 0 for name in ('underflows', 'overflows', 'lates')):
                    if ran_health != 'failed':
                        ran_health, reason = 'degraded', 'recent_radio_error_events'
        result["health"][stack] = dict(core=healthy({"amf", "smf", "upf", "nrf", "ausf", "udm", "udr", "pcf", "bsf", "nssf", "mongo"}),
                                      ran=ran_health, host=host, b210=b210)
        for c in result.get('components', []):
            if c['id'] == stack + ':gnb':
                c['health'] = ran_health
                c.setdefault('details', {})['health_reason'] = reason
    return result


def empty_snapshot():
    return dict(schema_version=SCHEMA_VERSION, observed_at=utc(), collector_status="unavailable",
                active_stack="unknown", observations=[], services=[], events=[], components=[], links=[], devices=[], health={})


def stale_entity(entity):
    result=copy.deepcopy(entity)
    result.update(state='unknown', status='stale')
    if 'registration' in result:
        result['last_registration']=result.get('last_registration',result['registration'])
        result['registration']='unknown'
    for item in result.get('metrics', []):
        if item['status']=='ok':
            item.update(status='stale', reason='entity_not_in_current_snapshot')
    for session in result.get('sessions', []):
        session['status']='stale'
    if 'registration' in result:
        from .connectivity import connection_state
        connection_state(result)
    return result


def rate(previous, current, elapsed):
    if previous is None or current < previous or elapsed <= 0:
        return None
    return (current - previous) * 8 / elapsed
