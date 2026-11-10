"""Create the SplitBox SQLite database from the SQLAlchemy models."""

from database import Base, DATABASE_PATH, engine
import models  # noqa: F401  (registers the tables with Base.metadata)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print(f"Initialised {DATABASE_PATH}")


if __name__ == "__main__":
    main()
