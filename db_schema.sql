-- MySQL dump 10.13  Distrib 8.0.34, for Linux (aarch64)
--
-- Host: localhost    Database: ClashRoyaleManager
-- ------------------------------------------------------
-- Server version	8.0.34-0ubuntu0.20.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `boat_battles`
--

DROP TABLE IF EXISTS `boat_battles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `boat_battles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `clan_affiliation_id` int NOT NULL,
  `river_race_id` int NOT NULL,
  `time` timestamp NOT NULL,
  `deck_id` int NOT NULL,
  `elixir_leaked` float NOT NULL,
  `new_towers_destroyed` tinyint NOT NULL,
  `prev_towers_destroyed` tinyint NOT NULL,
  `remaining_towers` tinyint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `clan_affiliation_id` (`clan_affiliation_id`),
  KEY `river_race_id` (`river_race_id`),
  KEY `deck_id` (`deck_id`),
  CONSTRAINT `boat_battles_ibfk_1` FOREIGN KEY (`clan_affiliation_id`) REFERENCES `clan_affiliations` (`id`),
  CONSTRAINT `boat_battles_ibfk_2` FOREIGN KEY (`river_race_id`) REFERENCES `river_races` (`id`),
  CONSTRAINT `boat_battles_ibfk_3` FOREIGN KEY (`deck_id`) REFERENCES `decks` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cards`
--

DROP TABLE IF EXISTS `cards`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cards` (
  `id` int NOT NULL,
  `name` varchar(64) NOT NULL,
  `max_level` tinyint NOT NULL,
  `url` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clan_affiliations`
--

DROP TABLE IF EXISTS `clan_affiliations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clan_affiliations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `clan_id` int NOT NULL,
  `role` enum('member','elder','coleader','leader') DEFAULT NULL,
  `first_joined` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`,`clan_id`),
  KEY `clan_id` (`clan_id`),
  CONSTRAINT `clan_affiliations_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `clan_affiliations_ibfk_2` FOREIGN KEY (`clan_id`) REFERENCES `clans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clan_role_discord_roles`
--

DROP TABLE IF EXISTS `clan_role_discord_roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clan_role_discord_roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `role` enum('member','elder','coleader','leader') NOT NULL,
  `discord_role_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clan_time`
--

DROP TABLE IF EXISTS `clan_time`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clan_time` (
  `id` int NOT NULL AUTO_INCREMENT,
  `clan_affiliation_id` int NOT NULL,
  `start` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `end` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `clan_affiliation_id` (`clan_affiliation_id`),
  CONSTRAINT `clan_time_ibfk_1` FOREIGN KEY (`clan_affiliation_id`) REFERENCES `clan_affiliations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clans`
--

DROP TABLE IF EXISTS `clans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clans` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tag` varchar(16) NOT NULL,
  `name` varchar(50) NOT NULL,
  `discord_role_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tag` (`tag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `deck_cards`
--

DROP TABLE IF EXISTS `deck_cards`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `deck_cards` (
  `deck_id` int NOT NULL,
  `card_id` int NOT NULL,
  `card_level` tinyint NOT NULL,
  PRIMARY KEY (`deck_id`,`card_id`),
  KEY `card_id` (`card_id`),
  CONSTRAINT `deck_cards_ibfk_1` FOREIGN KEY (`deck_id`) REFERENCES `decks` (`id`),
  CONSTRAINT `deck_cards_ibfk_2` FOREIGN KEY (`card_id`) REFERENCES `cards` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `decks`
--

DROP TABLE IF EXISTS `decks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `decks` (
  `id` int NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `duels`
--

DROP TABLE IF EXISTS `duels`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `duels` (
  `id` int NOT NULL AUTO_INCREMENT,
  `clan_affiliation_id` int NOT NULL,
  `river_race_id` int NOT NULL,
  `time` timestamp NOT NULL,
  `won` tinyint(1) NOT NULL,
  `battle_wins` tinyint NOT NULL,
  `battle_losses` tinyint NOT NULL,
  `round_1` int NOT NULL,
  `round_2` int NOT NULL,
  `round_3` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `clan_affiliation_id` (`clan_affiliation_id`),
  KEY `river_race_id` (`river_race_id`),
  KEY `round_1` (`round_1`),
  KEY `round_2` (`round_2`),
  KEY `round_3` (`round_3`),
  CONSTRAINT `duels_ibfk_1` FOREIGN KEY (`clan_affiliation_id`) REFERENCES `clan_affiliations` (`id`),
  CONSTRAINT `duels_ibfk_2` FOREIGN KEY (`river_race_id`) REFERENCES `river_races` (`id`),
  CONSTRAINT `duels_ibfk_3` FOREIGN KEY (`round_1`) REFERENCES `pvp_battles` (`id`),
  CONSTRAINT `duels_ibfk_4` FOREIGN KEY (`round_2`) REFERENCES `pvp_battles` (`id`),
  CONSTRAINT `duels_ibfk_5` FOREIGN KEY (`round_3`) REFERENCES `pvp_battles` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `kicks`
--

DROP TABLE IF EXISTS `kicks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `kicks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `clan_id` int NOT NULL,
  `time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `clan_id` (`clan_id`),
  CONSTRAINT `kicks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `kicks_ibfk_2` FOREIGN KEY (`clan_id`) REFERENCES `clans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `primary_clans`
--

DROP TABLE IF EXISTS `primary_clans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `primary_clans` (
  `clan_id` int NOT NULL,
  `track_stats` tinyint(1) NOT NULL,
  `send_reminders` tinyint(1) NOT NULL,
  `assign_strikes` tinyint(1) NOT NULL,
  `strike_type` enum('decks','medals') NOT NULL,
  `strike_threshold` int NOT NULL,
  `discord_channel_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`clan_id`),
  CONSTRAINT `primary_clans_ibfk_1` FOREIGN KEY (`clan_id`) REFERENCES `clans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pvp_battles`
--

DROP TABLE IF EXISTS `pvp_battles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pvp_battles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `clan_affiliation_id` int NOT NULL,
  `river_race_id` int NOT NULL,
  `time` timestamp NOT NULL,
  `game_type` varchar(50) NOT NULL,
  `won` tinyint(1) NOT NULL,
  `deck_id` int NOT NULL,
  `crowns` tinyint NOT NULL,
  `elixir_leaked` float NOT NULL,
  `kt_hit_points` smallint NOT NULL,
  `pt1_hit_points` smallint NOT NULL,
  `pt2_hit_points` smallint NOT NULL,
  `opp_deck_id` int NOT NULL,
  `opp_crowns` tinyint NOT NULL,
  `opp_elixir_leaked` float NOT NULL,
  `opp_kt_hit_points` smallint NOT NULL,
  `opp_pt1_hit_points` smallint NOT NULL,
  `opp_pt2_hit_points` smallint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `clan_affiliation_id` (`clan_affiliation_id`),
  KEY `river_race_id` (`river_race_id`),
  KEY `deck_id` (`deck_id`),
  KEY `opp_deck_id` (`opp_deck_id`),
  CONSTRAINT `pvp_battles_ibfk_1` FOREIGN KEY (`clan_affiliation_id`) REFERENCES `clan_affiliations` (`id`),
  CONSTRAINT `pvp_battles_ibfk_2` FOREIGN KEY (`river_race_id`) REFERENCES `river_races` (`id`),
  CONSTRAINT `pvp_battles_ibfk_3` FOREIGN KEY (`deck_id`) REFERENCES `decks` (`id`),
  CONSTRAINT `pvp_battles_ibfk_4` FOREIGN KEY (`opp_deck_id`) REFERENCES `decks` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `river_race_clans`
--

DROP TABLE IF EXISTS `river_race_clans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `river_race_clans` (
  `id` int NOT NULL AUTO_INCREMENT,
  `clan_id` int NOT NULL,
  `season_id` int NOT NULL,
  `tag` varchar(16) NOT NULL,
  `name` varchar(50) NOT NULL,
  `current_race_medals` int NOT NULL DEFAULT '0',
  `total_season_medals` int NOT NULL DEFAULT '0',
  `current_race_total_decks` int NOT NULL DEFAULT '0',
  `total_season_battle_decks` int NOT NULL DEFAULT '0',
  `battle_days` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `river_race_clans_ibfk_1` (`clan_id`),
  KEY `river_race_clans_ibfk_2` (`season_id`),
  CONSTRAINT `river_race_clans_ibfk_1` FOREIGN KEY (`clan_id`) REFERENCES `clans` (`id`),
  CONSTRAINT `river_race_clans_ibfk_2` FOREIGN KEY (`season_id`) REFERENCES `seasons` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `river_race_user_data`
--

DROP TABLE IF EXISTS `river_race_user_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `river_race_user_data` (
  `clan_affiliation_id` int NOT NULL,
  `river_race_id` int NOT NULL,
  `last_check` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `tracked_since` timestamp NULL DEFAULT NULL,
  `medals` int NOT NULL DEFAULT '0',
  `regular_wins` int NOT NULL DEFAULT '0',
  `regular_losses` int NOT NULL DEFAULT '0',
  `special_wins` int NOT NULL DEFAULT '0',
  `special_losses` int NOT NULL DEFAULT '0',
  `duel_wins` int NOT NULL DEFAULT '0',
  `duel_losses` int NOT NULL DEFAULT '0',
  `series_wins` int NOT NULL DEFAULT '0',
  `series_losses` int NOT NULL DEFAULT '0',
  `boat_wins` int NOT NULL DEFAULT '0',
  `boat_losses` int NOT NULL DEFAULT '0',
  `day_1` int DEFAULT NULL,
  `day_2` int DEFAULT NULL,
  `day_3` int DEFAULT NULL,
  `day_4` int DEFAULT NULL,
  `day_5` int DEFAULT NULL,
  `day_6` int DEFAULT NULL,
  `day_7` int DEFAULT NULL,
  `day_1_active` tinyint(1) DEFAULT NULL,
  `day_2_active` tinyint(1) DEFAULT NULL,
  `day_3_active` tinyint(1) DEFAULT NULL,
  `day_4_active` tinyint(1) DEFAULT NULL,
  `day_5_active` tinyint(1) DEFAULT NULL,
  `day_6_active` tinyint(1) DEFAULT NULL,
  `day_7_active` tinyint(1) DEFAULT NULL,
  `day_4_locked` tinyint(1) DEFAULT NULL,
  `day_5_locked` tinyint(1) DEFAULT NULL,
  `day_6_locked` tinyint(1) DEFAULT NULL,
  `day_7_locked` tinyint(1) DEFAULT NULL,
  `day_4_outside_battles` int DEFAULT NULL,
  `day_5_outside_battles` int DEFAULT NULL,
  `day_6_outside_battles` int DEFAULT NULL,
  `day_7_outside_battles` int DEFAULT NULL,
  PRIMARY KEY (`clan_affiliation_id`,`river_race_id`),
  KEY `river_race_id` (`river_race_id`),
  CONSTRAINT `river_race_user_data_ibfk_1` FOREIGN KEY (`clan_affiliation_id`) REFERENCES `clan_affiliations` (`id`),
  CONSTRAINT `river_race_user_data_ibfk_2` FOREIGN KEY (`river_race_id`) REFERENCES `river_races` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `river_races`
--

DROP TABLE IF EXISTS `river_races`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `river_races` (
  `id` int NOT NULL AUTO_INCREMENT,
  `clan_id` int NOT NULL,
  `season_id` int NOT NULL,
  `week` int NOT NULL,
  `start_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_check` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `battle_time` tinyint(1) NOT NULL DEFAULT '0',
  `colosseum_week` tinyint(1) NOT NULL DEFAULT '0',
  `completed_saturday` tinyint(1) NOT NULL DEFAULT '0',
  `day_1` timestamp NULL DEFAULT NULL,
  `day_2` timestamp NULL DEFAULT NULL,
  `day_3` timestamp NULL DEFAULT NULL,
  `day_4` timestamp NULL DEFAULT NULL,
  `day_5` timestamp NULL DEFAULT NULL,
  `day_6` timestamp NULL DEFAULT NULL,
  `day_7` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `clan_id` (`clan_id`,`season_id`,`week`),
  KEY `season_id` (`season_id`),
  CONSTRAINT `river_races_ibfk_1` FOREIGN KEY (`clan_id`) REFERENCES `clans` (`id`),
  CONSTRAINT `river_races_ibfk_2` FOREIGN KEY (`season_id`) REFERENCES `seasons` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `seasons`
--

DROP TABLE IF EXISTS `seasons`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `seasons` (
  `id` int NOT NULL AUTO_INCREMENT,
  `start_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `special_discord_channels`
--

DROP TABLE IF EXISTS `special_discord_channels`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_discord_channels` (
  `id` int NOT NULL AUTO_INCREMENT,
  `channel` enum('kicks','new_member_info','rules','strikes') NOT NULL,
  `discord_channel_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `channel` (`channel`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `special_discord_roles`
--

DROP TABLE IF EXISTS `special_discord_roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_discord_roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `role` enum('visitor','new') NOT NULL,
  `discord_role_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `discord_id` bigint unsigned DEFAULT NULL,
  `discord_name` varchar(50) DEFAULT NULL,
  `tag` varchar(16) NOT NULL,
  `name` varchar(50) NOT NULL,
  `strikes` int NOT NULL DEFAULT '0',
  `reminder_time` enum('NA','EU','ASIA') NOT NULL,
  `needs_update` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `tag` (`tag`),
  UNIQUE KEY `discord_id` (`discord_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `variables`
--

DROP TABLE IF EXISTS `variables`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `variables` (
  `initialized` tinyint(1) NOT NULL DEFAULT '0',
  `guild_id` bigint unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`initialized`,`guild_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

INSERT INTO `variables` VALUES (DEFAULT, DEFAULT);

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2023-08-30  7:03:50
