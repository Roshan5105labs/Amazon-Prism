from app.database import init_db


def seed() -> None:
    init_db()


if __name__ == "__main__":
    init_db()
    print("DB initialised.")
