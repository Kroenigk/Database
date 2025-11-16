-- National Parks Explorer Schema
-- Run: mysql -h host -u user -p DB_NAME < schema.sql

CREATE TABLE state (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(2) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE park (
    id INT AUTO_INCREMENT PRIMARY KEY,
    park_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    designation VARCHAR(255),
    description TEXT,
    url VARCHAR(500),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    phone VARCHAR(50),
    email VARCHAR(120),
    states_raw VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX (park_code),
    INDEX (name)
) ENGINE=InnoDB;

CREATE TABLE park_state (
    park_id INT NOT NULL,
    state_id INT NOT NULL,
    PRIMARY KEY (park_id, state_id),
    FOREIGN KEY (park_id) REFERENCES park(id) ON DELETE CASCADE,
    FOREIGN KEY (state_id) REFERENCES state(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE activity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    activity_code VARCHAR(40) UNIQUE,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (name)
) ENGINE=InnoDB;

CREATE TABLE park_activity (
    park_id INT NOT NULL,
    activity_id INT NOT NULL,
    PRIMARY KEY (park_id, activity_id),
    FOREIGN KEY (park_id) REFERENCES park(id) ON DELETE CASCADE,
    FOREIGN KEY (activity_id) REFERENCES activity(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE campground (
    id INT AUTO_INCREMENT PRIMARY KEY,
    park_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    reservation_url VARCHAR(500),
    regulations_url VARCHAR(500),
    data_json JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (park_id) REFERENCES park(id) ON DELETE CASCADE,
    INDEX (park_id),
    INDEX (name)
) ENGINE=InnoDB;

CREATE TABLE amenity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE campground_amenity (
    campground_id INT NOT NULL,
    amenity_id INT NOT NULL,
    PRIMARY KEY (campground_id, amenity_id),
    FOREIGN KEY (campground_id) REFERENCES campground(id) ON DELETE CASCADE,
    FOREIGN KEY (amenity_id) REFERENCES amenity(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE app_user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    is_active TINYINT(1) DEFAULT 1,
    INDEX (username),
    INDEX (email)
) ENGINE=InnoDB;

CREATE TABLE user_session (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_token VARCHAR(128) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    is_active TINYINT(1) DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    INDEX (user_id),
    INDEX (session_token)
) ENGINE=InnoDB;

CREATE TABLE activity_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id INT NULL,
    metadata JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE SET NULL,
    INDEX (action),
    INDEX (user_id)
) ENGINE=InnoDB;

-- Optional future table (favorites) - commented out
-- CREATE TABLE favorite (
--     user_id INT NOT NULL,
--     park_id INT NOT NULL,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     PRIMARY KEY (user_id, park_id),
--     FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
--     FOREIGN KEY (park_id) REFERENCES park(id) ON DELETE CASCADE
-- ) ENGINE=InnoDB;
