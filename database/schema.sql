-- SplitBox database schema (generated from the SQLAlchemy models).
-- Run: uv run python init_db.py

CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(20) NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	password_hash VARCHAR(128) NOT NULL, 
	password_salt VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE TABLE games (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	platform VARCHAR(60) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_games_user_id ON games (user_id);
CREATE TABLE categories (
	id INTEGER NOT NULL, 
	game_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(game_id) REFERENCES games (id) ON DELETE CASCADE
);
CREATE INDEX ix_categories_game_id ON categories (game_id);
CREATE TABLE splits (
	id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	target_ms INTEGER, 
	position INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE CASCADE
);
CREATE INDEX ix_splits_category_id ON splits (category_id);
CREATE TABLE runs (
	id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	started_at DATETIME NOT NULL, 
	finished_at DATETIME NOT NULL, 
	total_ms INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE CASCADE
);
CREATE INDEX ix_runs_category_id ON runs (category_id);
CREATE TABLE run_splits (
	id INTEGER NOT NULL, 
	run_id INTEGER NOT NULL, 
	split_id INTEGER, 
	name VARCHAR(80) NOT NULL, 
	position INTEGER NOT NULL, 
	segment_ms INTEGER NOT NULL, 
	cumulative_ms INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(split_id) REFERENCES splits (id) ON DELETE SET NULL
);
CREATE INDEX ix_run_splits_run_id ON run_splits (run_id);
