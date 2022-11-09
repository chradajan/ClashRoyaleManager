ALTER TABLE river_race_user_data
    ADD day_4_blocked enum('max_participation', 'previously_battled') DEFAULT NULL,
    ADD day_5_blocked enum('max_participation', 'previously_battled') DEFAULT NULL,
    ADD day_6_blocked enum('max_participation', 'previously_battled') DEFAULT NULL,
    ADD day_7_blocked enum('max_participation', 'previously_battled') DEFAULT NULL;
