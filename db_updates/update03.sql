CREATE TABLE deck_card (
    deck_id INT NOT NULL,
    card_id INT NOT NULL,
    card_level TINYINT NOT NULL,
    PRIMARY KEY (deck_id, card_id),
    FOREIGN KEY (deck_id) REFERENCES decks(id),
    FOREIGN KEY (card_id) REFERENCES cards(id)
);

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_1, card_1_level FROM decks;

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_2, card_2_level FROM decks;

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_3, card_3_level FROM decks;

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_4, card_4_level FROM decks;

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_5, card_5_level FROM decks;

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_6, card_6_level FROM decks;

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_7, card_7_level FROM decks;

INSERT INTO deck_card (deck_id, card_id, card_level)
    SELECT id, card_8, card_8_level FROM decks;

ALTER TABLE decks DROP FOREIGN KEY decks_ibfk_1,
                  DROP FOREIGN KEY decks_ibfk_2,
                  DROP FOREIGN KEY decks_ibfk_3,
                  DROP FOREIGN KEY decks_ibfk_4,
                  DROP FOREIGN KEY decks_ibfk_5,
                  DROP FOREIGN KEY decks_ibfk_6,
                  DROP FOREIGN KEY decks_ibfk_7,
                  DROP FOREIGN KEY decks_ibfk_8;

ALTER TABLE decks DROP COLUMN card_1,
                  DROP COLUMN card_1_level,
                  DROP COLUMN card_2,
                  DROP COLUMN card_2_level,
                  DROP COLUMN card_3,
                  DROP COLUMN card_3_level,
                  DROP COLUMN card_4,
                  DROP COLUMN card_4_level,
                  DROP COLUMN card_5,
                  DROP COLUMN card_5_level,
                  DROP COLUMN card_6,
                  DROP COLUMN card_6_level,
                  DROP COLUMN card_7,
                  DROP COLUMN card_7_level,
                  DROP COLUMN card_8,
                  DROP COLUMN card_8_level;
