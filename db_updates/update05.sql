ALTER TABLE river_race_user_data
    ADD day_4_locked BOOLEAN DEFAULT NULL,
    ADD day_5_locked BOOLEAN DEFAULT NULL,
    ADD day_6_locked BOOLEAN DEFAULT NULL,
    ADD day_7_locked BOOLEAN DEFAULT NULL,
    ADD day_4_outside_battles INT DEFAULT NULL,
    ADD day_5_outside_battles INT DEFAULT NULL,
    ADD day_6_outside_battles INT DEFAULT NULL,
    ADD day_7_outside_battles INT DEFAULT NULL;

UPDATE river_race_user_data SET day_4_locked = TRUE, last_check = last_check WHERE day_4_blocked = "max_participation";
UPDATE river_race_user_data SET day_5_locked = TRUE, last_check = last_check WHERE day_5_blocked = "max_participation";
UPDATE river_race_user_data SET day_6_locked = TRUE, last_check = last_check WHERE day_6_blocked = "max_participation";
UPDATE river_race_user_data SET day_7_locked = TRUE, last_check = last_check WHERE day_7_blocked = "max_participation";

UPDATE river_race_user_data SET day_4_outside_battles = 1, last_check = last_check WHERE day_4_blocked = "previously_battled";
UPDATE river_race_user_data SET day_5_outside_battles = 1, last_check = last_check WHERE day_5_blocked = "previously_battled";
UPDATE river_race_user_data SET day_6_outside_battles = 1, last_check = last_check WHERE day_6_blocked = "previously_battled";
UPDATE river_race_user_data SET day_7_outside_battles = 1, last_check = last_check WHERE day_7_blocked = "previously_battled";

ALTER TABLE river_race_user_data DROP COLUMN day_4_blocked, DROP COLUMN day_5_blocked, DROP COLUMN day_6_blocked, DROP COLUMN day_7_blocked;
