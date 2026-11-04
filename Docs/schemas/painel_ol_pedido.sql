-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: localhost    Database: painel_ol
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `pedido`
--

DROP TABLE IF EXISTS `pedido`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pedido` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `numero_pedido_ol` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Chave natural — número do pedido no sistema da indústria',
  `id_industria` int unsigned DEFAULT NULL,
  `nome_arquivo` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codigo_interno_erp` int DEFAULT NULL COMMENT 'Código do pedido no ERP após importação',
  `cnpj_cliente` char(14) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `condicao` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '0',
  `observacao` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Observação do pedido (posição 87-186 do cabeçalho, layout Close-Up)',
  `data_pedido` datetime DEFAULT NULL,
  `valor_total` decimal(15,2) DEFAULT NULL,
  `status_operacional` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status_erp` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `data_faturamento` datetime DEFAULT NULL COMMENT 'Data de faturamento do pedido; NULL enquanto não faturado',
  `data_cancelamento` datetime DEFAULT NULL COMMENT 'Data de cancelamento do pedido; NULL enquanto não cancelado',
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pedido_numero_ol` (`numero_pedido_ol`),
  UNIQUE KEY `uq_pedido_arquivo` (`nome_arquivo`),
  KEY `idx_pedido_industria` (`id_industria`),
  KEY `idx_pedido_cliente` (`cnpj_cliente`),
  KEY `idx_pedido_data` (`data_pedido`),
  KEY `idx_pedido_status_operacional` (`status_operacional`),
  KEY `idx_pedido_status_erp` (`status_erp`),
  CONSTRAINT `fk_pedido_industria` FOREIGN KEY (`id_industria`) REFERENCES `industria` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=81 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Pedidos recebidos via FTP. numero_pedido_ol é a chave de ligação com as demais tabelas.';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-06-15 15:53:16
