"""Trusted local operator provisioning. Passwords are prompted, never CLI arguments."""
import argparse
from getpass import getpass

from sqlalchemy.orm import Session

from app.auth.dependencies import ADMIN_PERMISSIONS
from app.core.config import Settings
from app.db.session import build_engine
from app.schemas.auth import RegisterRequest
from app.services.users import create_user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--permission', action='append', choices=sorted(ADMIN_PERMISSIONS), default=[])
    args = parser.parse_args()
    password = getpass('Administrator password (15–128 characters): ')
    if password != getpass('Confirm password: '):
        parser.exit(1, 'Passwords do not match.\n')
    try:
        data = RegisterRequest(email=args.email, password=password, full_name=args.name)
    except ValueError:
        parser.exit(1, 'Invalid email, name or password length.\n')
    engine = build_engine(Settings())
    try:
        with Session(engine, expire_on_commit=False) as db:
            user = create_user(db, email=data.email, password=data.password.get_secret_value(),
                               full_name=data.full_name, role='ADMIN', permissions=args.permission)
            if user is None:
                parser.exit(1, 'Account already exists; no privileges were changed.\n')
            print(f'Administrator created: {user.id}. Explicit permissions: {len(args.permission)}.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
