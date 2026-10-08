import json

from test_password_security import security_context, login
from app.core.security import verify_password
from app.models.identity import Project, Role, User
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.api.permissions import get_project_permissions
from app.services.permission_cache_service import invalidate_permissions_for_user

BASE = '/api/v1/security/admin/projects/project'


def setup_admin(client, sessions):
    with sessions() as db:
        db.get(Role, 'admin-role').permissions = 'identity.users.manage,records.read'
        db.commit()
    invalidate_permissions_for_user('admin')
    return {'Authorization': 'Bearer ' + login(client, 'admin@example.com', 'AdminPassword123')}


def test_create_user_is_atomic_unique_and_forces_password_change(security_context):
    client, sessions = security_context
    headers = setup_admin(client, sessions)
    payload = dict(full_name='Nueva Persona', document_id='new-doc', email='new@example.com', role_id='basic-role', admin_password='AdminPassword123')
    response = client.post(BASE + '/users', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created['user']['permissions'] == ['records.read']
    assert created['user']['must_change_password']
    with sessions() as db:
        user = db.get(User, created['user']['id'])
        assert verify_password(created['temporary_password'], user.password_hash)
        assert not verify_password('ChangeMe123', user.password_hash)
        assert db.query(UserProjectAssignment).filter_by(user_id=user.id, project_id='project').count() == 1
        logs = db.query(AuditLog).filter_by(entity_id=user.id).all()
        assert logs and created['temporary_password'] not in json.dumps([log.after_json for log in logs])
    assert client.post(BASE + '/users', headers=headers, json=payload).status_code == 409
    payload.update(email='other-new@example.com', document_id='other-new')
    second = client.post(BASE + '/users', headers=headers, json=payload)
    assert second.status_code == 201
    assert second.json()['temporary_password'] != created['temporary_password']


def test_access_change_invalidates_cache_and_preserves_other_projects(security_context):
    client, sessions = security_context
    headers = setup_admin(client, sessions)
    with sessions() as db:
        db.add(UserProjectAssignment(user_id='target', project_id='other-project', role_id='basic-role', status='active'))
        db.commit()
        assert 'records.read' in get_project_permissions(db, 'target', 'project')[1]
    payload = dict(role_id='basic-role', assignment_status='suspended', admin_password='AdminPassword123')
    result = client.patch(BASE + '/users/target/access', headers=headers, json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['permissions'] == []
    with sessions() as db:
        assert get_project_permissions(db, 'target', 'project')[1] == set()
        assert 'records.read' in get_project_permissions(db, 'target', 'other-project')[1]
        assert db.get(User, 'target').status == 'active'
    payload['assignment_status'] = 'active'
    assert client.patch(BASE + '/users/target/access', headers=headers, json=payload).status_code == 200
    assert client.patch(BASE + '/users/admin/access', headers=headers, json=payload).status_code == 409


def test_management_rejects_escalation_wrong_password_and_cross_project(security_context):
    client, sessions = security_context
    headers = setup_admin(client, sessions)
    with sessions() as db:
        db.add(Role(id='super-role', name='Superior', permissions='organizations.manage'))
        db.commit()
    payload = dict(role_id='super-role', assignment_status='active', admin_password='AdminPassword123')
    assert client.patch(BASE + '/users/target/access', headers=headers, json=payload).status_code == 403
    payload.update(role_id='basic-role', admin_password='incorrecta')
    assert client.patch(BASE + '/users/target/access', headers=headers, json=payload).status_code == 401
    assert client.get((BASE.rsplit('/', 1)[0] + '/other-project') + '/users', headers=headers).status_code == 403
    roles = client.get(BASE + '/roles', headers=headers).json()
    assert 'super-role' not in [role['id'] for role in roles]
    bad_role = dict(name='No permitido', permissions=['organizations.manage'], admin_password='AdminPassword123')
    assert client.post(BASE + '/roles', headers=headers, json=bad_role).status_code == 403
    bad_role.update(name='Consulta', permissions=['records.read'])
    assert client.post(BASE + '/roles', headers=headers, json=bad_role).status_code == 201
    basic_headers = {'Authorization': 'Bearer ' + login(client, 'target@example.com', 'TargetPassword123')}
    assert client.get(BASE + '/users', headers=basic_headers).status_code == 403


def test_legacy_assignments_cannot_bypass_scope_or_role_limits(security_context):
    client, sessions = security_context
    headers = setup_admin(client, sessions)
    with sessions() as db:
        db.add(Role(id='super-role', name='Superior', permissions='organizations.manage'))
        db.commit()
    payload = dict(user_id='outsider', project_id='other-project', role_id='basic-role')
    assert client.post('/api/v1/assignments/', headers=headers, json=payload).status_code == 403
    payload.update(project_id='project', role_id='super-role')
    assert client.post('/api/v1/assignments/', headers=headers, json=payload).status_code == 403
    payload['role_id'] = 'basic-role'
    assert client.post('/api/v1/assignments/', headers=headers, json=payload).status_code == 200
    assert client.post('/api/v1/assignments/', headers=headers, json=payload).status_code == 409
    rows = client.get('/api/v1/assignments/', headers=headers).json()
    assert all(row['project_id'] == 'project' for row in rows)


def test_account_resets_cannot_take_over_a_user_in_another_project(security_context):
    client, sessions = security_context
    headers = setup_admin(client, sessions)
    with sessions() as db:
        db.add(UserProjectAssignment(user_id='target', project_id='other-project', role_id='basic-role', status='active'))
        db.commit()
    password = {'admin_password': 'AdminPassword123'}
    for endpoint in ['password-reset', 'mfa-reset']:
        assert client.post(BASE + '/users/target/' + endpoint, headers=headers, json=password).status_code == 403
    assert client.patch(BASE + '/users/target/email', headers=headers, json={**password, 'email': 'changed@example.com'}).status_code == 403
    with sessions() as db:
        assert db.get(User, 'target').email == 'target@example.com'


def test_suspension_cannot_hide_inherited_organization_access(security_context):
    from app.models.assignment import UserOrganizationAssignment
    from app.models.organization import Organization
    client, sessions = security_context
    headers = setup_admin(client, sessions)
    with sessions() as db:
        db.add(Organization(id='org', name='Organización', slug='org'))
        db.add(Role(id='empty-role', name='Sin permisos', permissions=''))
        db.get(Project, 'project').organization_id = 'org'
        db.add(UserOrganizationAssignment(user_id='target', organization_id='org', role_id='empty-role', status='active'))
        db.commit()
    invalidate_permissions_for_user('target')
    payload = dict(role_id='basic-role', assignment_status='suspended', admin_password='AdminPassword123')
    assert client.patch(BASE + '/users/target/access', headers=headers, json=payload).status_code == 409
