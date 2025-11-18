-- National Parks Explorer Schema
-- Run: mysql -h host -u user -p DB_NAME < schema.sql

CREATE TABLE STATE (
    state_code CHAR(2) PRIMARY KEY,
    name       VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE PARK (
    park_id     CHAR(36) PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    designation VARCHAR(50),
    description TEXT,
    latitude    DECIMAL(9,6),
    longitude   DECIMAL(9,6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ACTIVITY (
    activity_id VARCHAR(50) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AMENITY (
    amenity_id INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE APP_USER (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL,
    email         VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'user',
    UNIQUE KEY uq_app_user_username (username),
    UNIQUE KEY uq_app_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- User tags and park tags
-- =========================================================

CREATE TABLE USER_TAG (
    tag_id  INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    label   VARCHAR(50) NOT NULL,
    CONSTRAINT fk_user_tag_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE PARK_TAG (
    park_id CHAR(36) NOT NULL,
    tag_id  INT      NOT NULL,
    PRIMARY KEY (park_id, tag_id),
    CONSTRAINT fk_park_tag_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_park_tag_tag
        FOREIGN KEY (tag_id) REFERENCES USER_TAG(tag_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Park / state / activity relationships
-- =========================================================

CREATE TABLE PARK_STATE (
    park_id    CHAR(36) NOT NULL,
    state_code CHAR(2)  NOT NULL,
    PRIMARY KEY (park_id, state_code),
    CONSTRAINT fk_park_state_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_park_state_state
        FOREIGN KEY (state_code) REFERENCES STATE(state_code)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE PARK_ACTIVITY (
    park_id     CHAR(36)    NOT NULL,
    activity_id VARCHAR(50) NOT NULL,
    PRIMARY KEY (park_id, activity_id),
    CONSTRAINT fk_park_activity_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_park_activity_activity
        FOREIGN KEY (activity_id) REFERENCES ACTIVITY(activity_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Events, images, alerts, trails
-- =========================================================

CREATE TABLE EVENT (
    event_id   INT AUTO_INCREMENT PRIMARY KEY,
    park_id    CHAR(36)      NOT NULL,
    title      VARCHAR(150)  NOT NULL,
    start_time DATETIME,
    end_time   DATETIME,
    CONSTRAINT fk_event_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IMAGE (
    image_id INT AUTO_INCREMENT PRIMARY KEY,
    park_id  CHAR(36)      NOT NULL,
    url      VARCHAR(255)  NOT NULL,
    alt_text VARCHAR(255),
    credit   VARCHAR(150),
    CONSTRAINT fk_image_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE PARK_ALERT (
    alert_id   INT AUTO_INCREMENT PRIMARY KEY,
    park_id    CHAR(36)     NOT NULL,
    category   VARCHAR(50),
    title      VARCHAR(150) NOT NULL,
    description TEXT,
    issued_at  DATETIME,
    expires_at DATETIME,
    CONSTRAINT fk_park_alert_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE TRAIL (
    trail_id     INT AUTO_INCREMENT PRIMARY KEY,
    park_id      CHAR(36)     NOT NULL,
    name         VARCHAR(150) NOT NULL,
    length_miles DECIMAL(5,2),
    difficulty   VARCHAR(20),
    CONSTRAINT fk_trail_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Campgrounds, facilities, fees, amenities, accessibility
-- =========================================================

CREATE TABLE CAMPGROUND (
    campground_id INT AUTO_INCREMENT PRIMARY KEY,
    park_id       CHAR(36)     NOT NULL,
    name          VARCHAR(150) NOT NULL,
    description   TEXT,
    latitude      DECIMAL(9,6),
    longitude     DECIMAL(9,6),
    CONSTRAINT fk_campground_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE CAMPGROUND_AMENITY (
    campground_id INT NOT NULL,
    amenity_id    INT NOT NULL,
    PRIMARY KEY (campground_id, amenity_id),
    CONSTRAINT fk_campground_amenity_campground
        FOREIGN KEY (campground_id) REFERENCES CAMPGROUND(campground_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_campground_amenity_amenity
        FOREIGN KEY (amenity_id) REFERENCES AMENITY(amenity_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE FACILITY (
    facility_id CHAR(36) PRIMARY KEY,
    park_id     CHAR(36),
    name        VARCHAR(255) NOT NULL,
    type        VARCHAR(50),
    CONSTRAINT fk_facility_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE FEE (
    fee_id      INT AUTO_INCREMENT PRIMARY KEY,
    facility_id CHAR(36) NOT NULL,
    description VARCHAR(255),
    amount      DECIMAL(10,2),
    CONSTRAINT fk_fee_facility
        FOREIGN KEY (facility_id) REFERENCES FACILITY(facility_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE FACILITY_ACTIVITY (
    facility_id CHAR(36) NOT NULL,
    activity_id VARCHAR(50) NOT NULL,
    PRIMARY KEY (facility_id, activity_id),
    CONSTRAINT fk_facility_activity_facility
        FOREIGN KEY (facility_id) REFERENCES FACILITY(facility_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_facility_activity_activity
        FOREIGN KEY (activity_id) REFERENCES ACTIVITY(activity_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ACCESSIBILITY (
    accessibility_id     INT AUTO_INCREMENT PRIMARY KEY,
    facility_id          CHAR(36) NOT NULL,
    wheelchair_accessible TINYINT(1) NOT NULL DEFAULT 0,
    audio_descriptions    TINYINT(1) NOT NULL DEFAULT 0,
    tactile_exhibits      TINYINT(1) NOT NULL DEFAULT 0,
    CONSTRAINT fk_accessibility_facility
        FOREIGN KEY (facility_id) REFERENCES FACILITY(facility_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Weather & safety
-- =========================================================

CREATE TABLE WEATHER (
    weather_id  INT AUTO_INCREMENT PRIMARY KEY,
    park_id     CHAR(36) NOT NULL,
    record_date DATE     NOT NULL,
    temp_high   DECIMAL(5,2),
    temp_low    DECIMAL(5,2),
    precip_mm   DECIMAL(6,2),
    CONSTRAINT fk_weather_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE,
    UNIQUE KEY uq_weather_park_date (park_id, record_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE SAFETY (
    safety_id             INT AUTO_INCREMENT PRIMARY KEY,
    park_id               CHAR(36) NOT NULL,
    safety_score          DECIMAL(4,2),
    earthquake_risk_level TINYINT,
    weather_risk_level    TINYINT,
    last_updated          DATETIME,
    CONSTRAINT fk_safety_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE,
    UNIQUE KEY uq_safety_park (park_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Auth, sessions, logs
-- =========================================================

CREATE TABLE USER_SESSION (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT      NOT NULL,
    login_time DATETIME NOT NULL,
    logout_time DATETIME,
    CONSTRAINT fk_session_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ACTIVITY_LOG (
    log_id      INT AUTO_INCREMENT PRIMARY KEY,
    session_id  INT      NOT NULL,
    user_id     INT      NOT NULL,
    action_time DATETIME NOT NULL,
    action      VARCHAR(255) NOT NULL,
    CONSTRAINT fk_activity_log_session
        FOREIGN KEY (session_id) REFERENCES USER_SESSION(session_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_activity_log_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- User interactions with parks/campgrounds/trails
-- =========================================================

CREATE TABLE FAVORITE_PARK (
    user_id  INT      NOT NULL,
    park_id  CHAR(36) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, park_id),
    CONSTRAINT fk_favorite_park_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_favorite_park_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE RESERVATION (
    reservation_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT NOT NULL,
    campground_id  INT NOT NULL,
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    status         VARCHAR(20) NOT NULL,
    CONSTRAINT fk_reservation_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_reservation_campground
        FOREIGN KEY (campground_id) REFERENCES CAMPGROUND(campground_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE TRIP_LOG (
    trip_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT      NOT NULL,
    park_id    CHAR(36) NOT NULL,
    start_date DATE,
    end_date   DATE,
    notes      TEXT,
    CONSTRAINT fk_trip_log_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_trip_log_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE PARK_REVIEW (
    review_id   INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT      NOT NULL,
    park_id     CHAR(36) NOT NULL,
    rating      TINYINT  NOT NULL,
    review_text TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_park_review_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_park_review_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_park_review_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE WISHLIST_TRIP (
    wishlist_id   INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT      NOT NULL,
    park_id       CHAR(36) NOT NULL,
    target_season VARCHAR(20),
    notes         TEXT,
    CONSTRAINT fk_wishlist_trip_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_wishlist_trip_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE TRAIL_REVIEW (
    review_id   INT AUTO_INCREMENT PRIMARY KEY,
    trail_id    INT NOT NULL,
    user_id     INT NOT NULL,
    rating      TINYINT NOT NULL,
    review_text TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_trail_review_trail
        FOREIGN KEY (trail_id) REFERENCES TRAIL(trail_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_trail_review_user
        FOREIGN KEY (user_id) REFERENCES APP_USER(user_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_trail_review_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Analytics table
-- =========================================================

CREATE TABLE PARK_POPULARITY (
    park_id          CHAR(36) PRIMARY KEY,
    favorites_count  INT      NOT NULL DEFAULT 0,
    visit_count      INT      NOT NULL DEFAULT 0,
    review_count     INT      NOT NULL DEFAULT 0,
    avg_rating       DECIMAL(3,2),
    last_updated     DATETIME,
    CONSTRAINT fk_park_popularity_park
        FOREIGN KEY (park_id) REFERENCES PARK(park_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
