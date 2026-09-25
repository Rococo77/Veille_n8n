"""Amorçage : création du premier administrateur.

Usage : veille-admin create-admin --email admin@example.com
Le mot de passe est demandé de façon interactive (jamais en argument : il finirait
dans l'historique du shell et dans `ps`).
"""

import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError

from veille.config import get_settings
from veille.db import build_engine, build_sessionmaker
from veille.errors import DomainError
from veille.schemas import UserIn
from veille.services import users


async def _create_admin(email: str, password: str) -> None:
    engine = build_engine(get_settings().database_url)
    try:
        async with build_sessionmaker(engine)() as db:
            created = await users.create_user(
                db, UserIn(email=email, password=password, role="admin"), actor=None, ip=None
            )
            print(f"Admin créé : {created.email}. Second facteur à configurer à la 1re connexion.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="veille-admin")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin")
    create.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Mot de passe (12 caractères min.) : ")
    if password != getpass.getpass("Confirmation : "):
        sys.exit("Les mots de passe ne correspondent pas.")
    try:
        asyncio.run(_create_admin(args.email, password))
    except ValidationError as exc:
        sys.exit(f"Entrée invalide : {exc.errors()[0]['msg']}")
    except DomainError as exc:
        sys.exit(f"{exc.title} : {exc.detail}")


if __name__ == "__main__":
    main()
