-- MySQL dump 10.13  Distrib 8.0.29, for Linux (aarch64)
--
-- Host: localhost    Database: ClashRoyaleManager
-- ------------------------------------------------------
-- Server version	8.0.29-0ubuntu0.20.04.3

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
-- Table structure for table `clans_in_race`
--

DROP TABLE IF EXISTS `clans_in_race`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clans_in_race` (
  `river_race_id` int NOT NULL,
  `river_race_clan_id` int NOT NULL,
  PRIMARY KEY (`river_race_id`,`river_race_clan_id`),
  KEY `river_race_clan_id` (`river_race_clan_id`),
  CONSTRAINT `clans_in_race_ibfk_1` FOREIGN KEY (`river_race_id`) REFERENCES `river_races` (`id`),
  CONSTRAINT `clans_in_race_ibfk_2` FOREIGN KEY (`river_race_clan_id`) REFERENCES `river_race_clans` (`id`)
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
  `time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `kicks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
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
  PRIMARY KEY (`clan_id`),
  CONSTRAINT `primary_clans_ibfk_1` FOREIGN KEY (`clan_id`) REFERENCES `clans` (`id`)
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
  `season_id` int NOT NULL,
  `tag` varchar(16) NOT NULL,
  `name` varchar(50) NOT NULL,
  `current_race_medals` int NOT NULL DEFAULT '0',
  `total_season_medals` int NOT NULL DEFAULT '0',
  `current_race_total_decks` int NOT NULL DEFAULT '0',
  `total_season_battle_decks` int NOT NULL DEFAULT '0',
  `battle_days` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `season_id` (`season_id`),
  CONSTRAINT `river_race_clans_ibfk_1` FOREIGN KEY (`season_id`) REFERENCES `seasons` (`id`)
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
  `tracked_since` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
  `start_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `colosseum_week` tinyint(1) NOT NULL DEFAULT '0',
  `completed_saturday` tinyint(1) NOT NULL DEFAULT '0',
  `week` int NOT NULL,
  `day_1` timestamp NULL DEFAULT NULL,
  `day_2` timestamp NULL DEFAULT NULL,
  `day_3` timestamp NULL DEFAULT NULL,
  `day_4` timestamp NULL DEFAULT NULL,
  `day_5` timestamp NULL DEFAULT NULL,
  `day_6` timestamp NULL DEFAULT NULL,
  `day_7` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `clan_id` (`clan_id`,`season_id`),
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
  `channel` enum('strikes','reminders','admin_only') NOT NULL,
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
  `role` enum('visitor','new','admin') NOT NULL,
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
  `reminder_time` enum('US','EU') NOT NULL,
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
  `last_check` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`initialized`,`guild_id`,`last_check`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

INSERT INTO `variables` VALUES (DEFAULT, DEFAULT, DEFAULT);

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2022-05-13 22:22:59
