"""Set up a Globus project and exchange for Academy testing.

Step 1: Lists existing projects
Step 2: Creates a new 'Academy Dev' project (or reuse existing)
Step 3: Registers an exchange client + credentials + scope under it
Step 4: Prints the env vars needed for GlobusExchangeFactory

Uses cached credentials from prior Globus login.

Usage:
    PYTHONPATH=. python examples/check_projects.py
"""
from __future__ import annotations

from globus_sdk import AuthClient
from globus_sdk import DependentScopeSpec
from globus_sdk.gare import GlobusAuthorizationParameters
from globus_sdk.scopes import AuthScopes

from academy.exchange.cloud.login import get_user_app


def main() -> int:
    app = get_user_app()

    app.add_scope_requirements(
        {
            AuthScopes.resource_server: [
                AuthScopes.manage_projects,
                AuthScopes.email,
                AuthScopes.profile,
            ],
        },
    )

    auth_client = AuthClient(app=app)

    userinfo = auth_client.userinfo()
    identity_id = userinfo['sub']
    email = userinfo['preferred_username']
    print(f'Logged in as: {email}')
    print(f'Identity ID:  {identity_id}')
    print()

    # ── List existing projects ────────────────────────────────
    projects = list(auth_client.get_projects())
    if projects:
        print(f'Existing projects ({len(projects)}):')
        for i, p in enumerate(projects):
            is_admin = identity_id in p.get('admin_ids', [])
            marker = ' (you are admin)' if is_admin else ''
            print(f'  [{i}] {p["display_name"]} — {p["id"]}{marker}')
        print()

    # ── Create or select project ──────────────────────────────
    choice = input(
        'Enter [n] to create a new Academy project, '
        'or a number to use an existing one: ',
    ).strip()

    if choice.lower() == 'n':
        print()
        print('Creating new project "Academy Dev"...')
        resp = auth_client.create_project(
            'Academy Dev',
            contact_email=email,
            admin_ids=identity_id,
        )
        project_id = resp['project']['id']
        print(f'Created project: {project_id}')
    else:
        try:
            project_id = projects[int(choice)]['id']
        except (ValueError, IndexError):
            print('Invalid selection.')
            return 1
    print()

    # ── Fresh login for project admin operations ───────────────
    # Globus requires admin identity in session within last 30 min
    print('Re-authenticating (required for project admin ops)...')
    app.login(
        force=True,
        auth_params=GlobusAuthorizationParameters(prompt='login'),
    )
    # Recreate auth_client with fresh tokens
    auth_client = AuthClient(app=app)
    print('Done.')
    print()

    # ── Register exchange client ──────────────────────────────
    print('Registering exchange client...')
    client_resp = auth_client.create_client(
        'academy_exchange_dev',
        project=project_id,
        client_type='hybrid_confidential_client_resource_server',
        visibility='private',
    )
    client_id = client_resp['client']['id']
    print(f'  Client ID: {client_id}')

    # Create secret
    cred_resp = auth_client.create_client_credential(
        client_id,
        'academy_exchange_dev_creds',
    )
    secret = cred_resp['credential']['secret']
    print(f'  Secret:    {secret[:8]}...')

    # Create scope with dependent scope on Globus Groups
    groups_scope_spec = DependentScopeSpec(
        '73320ffe-4cb4-4b25-a0a3-83d53d59ce4f',
        optional=True,
        requires_refresh_token=False,
    )
    scope_resp = auth_client.create_scope(
        client_id,
        'Agent registration',
        'Send messages on the exchange',
        'academy_exchange',
        allows_refresh_token=True,
        dependent_scopes=[groups_scope_spec],
    )
    scope_id = scope_resp['scopes'][0]['id']
    print(f'  Scope ID:  {scope_id}')

    # ── Print env vars ────────────────────────────────────────
    print()
    print('=' * 50)
    print('Add these to your shell or .env:')
    print('=' * 50)
    print(f'export ACADEMY_TEST_PROJECT_ID={project_id}')
    print(f'export ACADEMY_EXCHANGE_CLIENT_ID={client_id}')
    print(f'export ACADEMY_EXCHANGE_SECRET={secret}')
    print(f'export ACADEMY_EXCHANGE_SCOPE_ID={scope_id}')
    print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
