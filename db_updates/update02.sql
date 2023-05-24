CREATE TABLE cards (
    id INT NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    max_level TINYINT NOT NULL,
    url VARCHAR(255) NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE decks (
    id INT NOT NULL AUTO_INCREMENT,
    card_1 INT NOT NULL,
    card_1_level TINYINT NOT NULL,
    card_2 INT NOT NULL,
    card_2_level TINYINT NOT NULL,
    card_3 INT NOT NULL,
    card_3_level TINYINT NOT NULL,
    card_4 INT NOT NULL,
    card_4_level TINYINT NOT NULL,
    card_5 INT NOT NULL,
    card_5_level TINYINT NOT NULL,
    card_6 INT NOT NULL,
    card_6_level TINYINT NOT NULL,
    card_7 INT NOT NULL,
    card_7_level TINYINT NOT NULL,
    card_8 INT NOT NULL,
    card_8_level TINYINT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (card_1) REFERENCES cards(id),
    FOREIGN KEY (card_2) REFERENCES cards(id),
    FOREIGN KEY (card_3) REFERENCES cards(id),
    FOREIGN KEY (card_4) REFERENCES cards(id),
    FOREIGN KEY (card_5) REFERENCES cards(id),
    FOREIGN KEY (card_6) REFERENCES cards(id),
    FOREIGN KEY (card_7) REFERENCES cards(id),
    FOREIGN KEY (card_8) REFERENCES cards(id),
    UNIQUE KEY (card_1, card_1_level, card_2, card_2_level, card_3, card_3_level, card_4, card_4_level, card_5, card_5_level, card_6, card_6_level, card_7, card_7_level, card_8, card_8_level)
);

CREATE TABLE pvp_battles (
    id INT NOT NULL AUTO_INCREMENT,
    clan_affiliation_id INT NOT NULL,
    river_race_id INT NOT NULL,
    time TIMESTAMP NOT NULL,
    game_type VARCHAR(50) NOT NULL,
    won BOOLEAN NOT NULL,
    deck_id INT NOT NULL,
    crowns TINYINT NOT NULL,
    elixir_leaked FLOAT NOT NULL,
    kt_hit_points SMALLINT NOT NULL,
    pt1_hit_points SMALLINT NOT NULL,
    pt2_hit_points SMALLINT NOT NULL,
    opp_deck_id INT NOT NULL,
    opp_crowns TINYINT NOT NULL,
    opp_elixir_leaked FLOAT NOT NULL,
    opp_kt_hit_points SMALLINT NOT NULL,
    opp_pt1_hit_points SMALLINT NOT NULL,
    opp_pt2_hit_points SMALLINT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (clan_affiliation_id) REFERENCES clan_affiliations(id),
    FOREIGN KEY (river_race_id) REFERENCES river_races(id),
    FOREIGN KEY (deck_id) REFERENCES decks(id),
    FOREIGN KEY (opp_deck_id) REFERENCES decks(id)
);

CREATE TABLE duels (
    id INT NOT NULL AUTO_INCREMENT,
    clan_affiliation_id INT NOT NULL,
    river_race_id INT NOT NULL,
    time TIMESTAMP NOT NULL,
    won BOOLEAN NOT NULL,
    battle_wins TINYINT NOT NULL,
    battle_losses TINYINT NOT NULL,
    round_1 INT NOT NULL,
    round_2 INT NOT NULL,
    round_3 INT DEFAULT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (clan_affiliation_id) REFERENCES clan_affiliations(id),
    FOREIGN KEY (river_race_id) REFERENCES river_races(id),
    FOREIGN KEY (round_1) REFERENCES pvp_battles(id),
    FOREIGN KEY (round_2) REFERENCES pvp_battles(id),
    FOREIGN KEY (round_3) REFERENCES pvp_battles(id)
);

CREATE TABLE boat_battles (
    id INT NOT NULL AUTO_INCREMENT,
    clan_affiliation_id INT NOT NULL,
    river_race_id INT NOT NULL,
    time TIMESTAMP NOT NULL,
    deck_id INT NOT NULL,
    elixir_leaked FLOAT NOT NULL,
    new_towers_destroyed TINYINT NOT NULL,
    prev_towers_destroyed TINYINT NOT NULL,
    remaining_towers TINYINT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (clan_affiliation_id) REFERENCES clan_affiliations(id),
    FOREIGN KEY (river_race_id) REFERENCES river_races(id),
    FOREIGN KEY (deck_id) REFERENCES decks(id)
);
