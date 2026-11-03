import hashlib
import hmac
import json
import time

import pytest
from werkzeug.security import generate_password_hash

from pmo import create_app
from pmo.models import Requirement, User


SECRET = 'nomi-person-lifecycle-test-secret'


def event(user_id, *, event_id='evt-offboard-1', event_type='person.offboarded', revision=1, action='offboard', status='inactive'):
    return {
        'event_id': event_id, 'event_type': event_type, 'event_version': 1,
        'tenant_id': 'tenant-hengjian', 'source_system': 'M01_KERNEL',
        'object_type': 'Person', 'object_id': str(user_id), 'revision': revision,
        'occurred_at': '2026-11-03T02:00:00Z', 'effective_at': '2026-11-03T02:00:00Z',
        'correlation_id': event_id, 'trace_id': event_id,
        'idempotency_key': f'tenant-hengjian:Person:{user_id}:{revision}:{event_type}',
        'person': {'person_id': str(user_id), 'emp_code': 'E001'},
        'status': status, 'employment_action': action, 'occurred_by': '朱剑军',
    }


def signed_headers(body):
    raw = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
    timestamp = str(int(time.time() * 1000))
    signature = hmac.new(SECRET.encode(), timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    return {'Content-Type': 'application/json', 'X-AEOS-Key-Id': 'm01-kernel',
            'X-AEOS-Timestamp': timestamp, 'X-AEOS-Signature': signature}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('AEOS_PERSON_LIFECYCLE_SECRET', SECRET)
    monkeypatch.setenv('AEOS_PERSON_LIFECYCLE_KEY_ID', 'm01-kernel')
    application = create_app({'TESTING': True, 'DATABASE_URL': f'sqlite:///{tmp_path / "nomi.db"}'})
    with application.extensions['sessions']() as db:
        user = User(username='E001', password_hash=generate_password_hash('secret'), role='member')
        db.add(user)
        db.flush()
        db.add(Requirement(project_id=1, key='REQ-LIFE', title='离职人员事项', module='测试', owner='E001', priority='P1', status='TODO', week=1))
        db.commit()
        user_id = user.id
    application.config['TEST_PERSON_ID'] = user_id
    return application


def post(app, body):
    raw = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
    return app.test_client().post('/internal/aeos/person-lifecycle', data=raw, headers=signed_headers(body))


def test_offboard_rejects_login_and_moves_project_ownership(app):
    person_id = app.config['TEST_PERSON_ID']
    client = app.test_client()
    assert client.post('/api/auth/login', json={'username': 'E001', 'password': 'secret'}, headers={'X-PMO-Request': '1'}).status_code == 200
    response = post(app, event(person_id))
    assert response.status_code == 200
    assert response.get_json()['status'] == 'synced'
    assert client.get('/api/auth/me').status_code == 401
    with app.extensions['sessions']() as db:
        row = db.query(Requirement).filter_by(key='REQ-LIFE').one()
        assert row.owner == '待重新分配'


def test_reinstate_restores_login_only_and_keeps_ownership_pending(app):
    person_id = app.config['TEST_PERSON_ID']
    assert post(app, event(person_id)).status_code == 200
    response = post(app, event(person_id, event_id='evt-reinstate-1', event_type='person.reinstated', revision=2, action='rehire', status='active'))
    assert response.status_code == 200
    assert response.get_json()['status'] == 'pending_confirmation'
    assert response.get_json()['pending_confirmation'] == {'permissions': True, 'agents': True}
    assert app.test_client().post('/api/auth/login', json={'username': 'E001', 'password': 'secret'}, headers={'X-PMO-Request': '1'}).status_code == 200


def test_replay_is_idempotent(app):
    body = event(app.config['TEST_PERSON_ID'])
    assert post(app, body).status_code == 200
    replay = post(app, body)
    assert replay.status_code == 200
    assert replay.get_json()['duplicate'] is True
