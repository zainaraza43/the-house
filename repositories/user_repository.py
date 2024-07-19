from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, discord_account_id: int):
        user = User(discord_account_id=discord_account_id)
        self.db.add(user)
        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise
        return user

    def get_user_by_discord_account_id(self, discord_account_id: int):
        return self.db.query(User).filter(User.discord_account_id == discord_account_id).first()
