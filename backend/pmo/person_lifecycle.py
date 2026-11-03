"""M01 人员离职/复职同步：只关闭当前访问和负责人关系，不删除历史。"""

import hashlib
import hmac
import os
import time

from flask import jsonify, request, g
from sqlalchemy import select

from .models import Requirement, SystemSetting, User


def _setting(db, key):
    return db.get(SystemSetting, key)


def is_user_active(db, user):
    row = _setting(db, f'person-lifecycle:user:{user.id}')
    return not row or (row.data or {}).get('status', 'active') == 'active'


def _verify():
    key_id = request.headers.get('X-AEOS-Key-Id', '')
    timestamp = request.headers.get('X-AEOS-Timestamp', '')
    signature = request.headers.get('X-AEOS-Signature', '').removeprefix('sha256=')
    if not key_id or key_id != os.getenv('AEOS_PERSON_LIFECYCLE_KEY_ID', 'm01-kernel') or not timestamp or not signature:
        return False
    try:
        timestamp_ms = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time() * 1000) - timestamp_ms) > int(os.getenv('AEOS_PERSON_LIFECYCLE_MAX_SKEW_SECONDS', '300')) * 1000:
        return False
    secret = os.getenv('AEOS_PERSON_LIFECYCLE_SECRET', '')
    raw = request.get_data(cache=True)
    expected = hmac.new(secret.encode(), timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature)


def apply_person_lifecycle(db, payload):
    for field in ('event_id', 'event_type', 'tenant_id', 'object_id', 'revision', 'idempotency_key', 'person'):
        if payload.get(field) in (None, ''):
            return {'status': 'failed', 'error': f'缺少必填字段：{field}'}, 400
    event_key = f'person-lifecycle:event:{payload["idempotency_key"]}'
    previous = _setting(db, event_key)
    if previous:
        result = dict(previous.data.get('result') or {})
        result['duplicate'] = True
        return result, 200
    person = payload.get('person') or {}
    emp_code = str(person.get('emp_code') or '').strip()
    object_id = str(payload['object_id'])
    candidates = db.scalars(select(User).where((User.username == emp_code) | (User.id == int(object_id) if object_id.isdigit() else User.id == -1))).all()
    if not candidates:
        return {'status': 'failed', 'error': '找不到对应人员，未执行停用'}, 404
    if len(candidates) != 1:
        return {'status': 'failed', 'error': '人员身份冲突，未执行停用'}, 409
    user = candidates[0]
    current = _setting(db, f'person-lifecycle:user:{user.id}')
    if current and int(payload['revision']) < int((current.data or {}).get('revision', 0)):
        return {'status': 'stale', 'state': 'stale', 'event_id': payload['event_id'], 'duplicate': False}, 200
    reassigned = []
    if payload['event_type'] == 'person.offboarded':
        state = {'person_id': object_id, 'emp_code': emp_code, 'status': 'inactive', 'revision': int(payload['revision'])}
        names = {user.username, emp_code}
        for row in db.scalars(select(Requirement).where(Requirement.owner.in_(names), Requirement.active == 1)).all():
            row.owner = '待重新分配'
            reassigned.append(row.key)
        result = {'status': 'synced', 'state': 'offboarded', 'event_id': payload['event_id'], 'duplicate': False,
                  'closed_items': ['login', 'project_owner', 'requirement_assignment'], 'reassigned_tasks': reassigned,
                  'pending_confirmation': {'permissions': False, 'agents': False}}
    elif payload['event_type'] == 'person.reinstated':
        state = {'person_id': object_id, 'emp_code': emp_code, 'status': 'active', 'revision': int(payload['revision'])}
        result = {'status': 'pending_confirmation', 'state': 'active', 'event_id': payload['event_id'], 'duplicate': False,
                  'closed_items': [], 'reassigned_tasks': [], 'pending_confirmation': {'permissions': True, 'agents': True}}
    else:
        return {'status': 'failed', 'error': f'不支持的人员状态事件：{payload["event_type"]}'}, 400
    db.merge(SystemSetting(key=f'person-lifecycle:user:{user.id}', data=state))
    db.merge(SystemSetting(key=event_key, data={'result': result, 'event_type': payload['event_type']}))
    db.commit()
    return result, 200


def register_person_lifecycle(app):
    @app.post('/internal/aeos/person-lifecycle')
    def person_lifecycle():
        if not _verify():
            return jsonify(error='人员同步签名无效'), 401
        payload = request.get_json(silent=True) or {}
        result, status = apply_person_lifecycle(g.db, payload)
        return jsonify(result), status

