import type { Device, Snapshot } from './types';

const recent = (at: string, seconds: number, now: number) => {
  const age = now - Date.parse(at);
  return Number.isFinite(age) && age >= -5000 && age <= seconds * 1000;
};

export function freshDevice(input: Device, available: boolean, now = Date.now()): Device {
  const d = structuredClone(input);
  const radio = d.source === 'ocudu_scheduler';
  if (!available || !recent(d.observed_at, radio ? 20 : 90, now)) {
    d.status = 'stale'; d.state = 'unknown'; d.registration = 'unknown';
    if (d.connection) {
      d.connection.state = 'unknown';
      d.connection.reason = 'sample_expired';
      for (const k in d.connection.layers) d.connection.layers[k] = 'unverified';
    }
  }
  for (const s of d.sessions) if (d.status !== 'ok' || d.registration === 'deregistered' || !recent(s.observed_at, 90, now)) s.status = 'stale';
  if (d.connection) {
    delete d.connection.layers.jetson_data;
    delete d.connection.layers.spark_ue_address;
    d.connection.layers.data_pdu = d.sessions.some(s => s.dnn === 'oai' && s.status === 'ok') ? 'recent_report' : 'unverified';
  }
  if (!radio && d.status === 'ok') {
    d.state = d.registration === 'registered' ? 'registered' : d.registration === 'deregistered' ? 'disconnected' : 'unknown';
    if (d.connection) d.connection.state = d.state;
  }
  for (const m of d.metrics) if (m.status === 'ok' && (!available || !recent(m.observed_at, 20, now))) m.status = 'stale';
  if (d.reachability && (!available || !recent(d.reachability.observed_at, 20, now))) {
    d.reachability.state = 'unknown';
  }
  return d;
}

export function freshView(input: Snapshot | null, connected: boolean, received: number, now: number): Snapshot | null {
  if (!input) return null;
  const s = structuredClone(input);
  const available = connected && now - received <= 20000 && recent(s.observed_at, 20, now) && s.collector_status === 'ok';
  if (!available) {
    s.collector_status = 'stale'; s.last_active_stack ||= s.active_stack; s.active_stack = 'unknown';
    for (const service of s.services) Object.assign(service, {state: 'stale', health: 'unknown', status: 'stale'});
    for (const states of Object.values(s.health || {})) for (const key in states) states[key] = 'unknown';
  }
  for (const m of s.observations) if (m.status === 'ok' && (!available || !recent(m.observed_at, 20, now))) m.status = 'stale';
  for (const c of [...s.components || [], ...s.links || []]) {
    if (!available) Object.assign(c, {state: 'unknown', health: 'unknown', business_health: 'unknown', status: 'stale'});
    if (!available && c.details && 'health_reason' in c.details) c.details.health_reason = 'sample_expired';
    for (const m of c.metrics) if (m.status === 'ok' && (!available || !recent(m.observed_at, 20, now))) m.status = 'stale';
  }
  s.devices = s.devices?.map(d => freshDevice(d, available, now));
  return s;
}
