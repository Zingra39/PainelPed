-- =====================================================================
-- create_homologacao_schema.sql
--
-- Cria a ESTRUTURA (schema, sem dados) do banco painel_ol_homologacao
-- no MySQL local, a partir das definicoes documentadas em Docs/schemas/.
--
-- USO RECOMENDADO: use setup_homologacao.ps1 (mysqldump do painel_ol
-- atual) para ter estrutura + dados reais em um unico passo.
--
-- Este script serve como:
--   (a) fallback caso mysqldump nao esteja disponivel, ou
--   (b) opcao para subir um homologacao 100% vazio (so estrutura).
--
-- NAO mexe no SQL Server / ERP. Roda apenas contra o MySQL local.
--
-- Gerado em: 2026-09-02, com base nos dumps de estrutura em
-- Docs/schemas/painel_ol_*.sql (a fonte de verdade fica sempre nesses
-- arquivos individuais; atualize-os quando o schema mudar).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS painel_ol_homologacao
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE painel_ol_homologacao;

SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- perfil
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `perfil`;
CREATE TABLE `perfil` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `permissoes` json DEFAULT NULL,
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_perfil_nome` (`nome`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Perfis de acesso: Administrador, Operador Logístico, Gerente Comercial';

-- ---------------------------------------------------------------------
-- usuario
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `usuario`;
CREATE TABLE `usuario` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `id_perfil` int unsigned DEFAULT NULL,
  `nome` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `senha_hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ativo` tinyint(1) DEFAULT '1',
  `ultimo_acesso` datetime DEFAULT NULL,
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_usuario_email` (`email`),
  KEY `fk_usuario_perfil` (`id_perfil`),
  CONSTRAINT `fk_usuario_perfil` FOREIGN KEY (`id_perfil`) REFERENCES `perfil` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Usuários do sistema';

-- ---------------------------------------------------------------------
-- industria
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `industria`;
CREATE TABLE `industria` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cnpj` char(14) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo_layout` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `id_bbs` int unsigned DEFAULT NULL,
  `pasta_envio` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pasta_envio_retorno` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pasta_envio_nf` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pasta_pedido_original` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pasta_entrada` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pasta_retorno` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pasta_nfe` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pasta_backup` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ativo` tinyint(1) DEFAULT '1',
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_industria_cnpj` (`cnpj`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Indústrias integradas: Hypera, EMS, Eurofarma, etc.';

-- ---------------------------------------------------------------------
-- industria_ftp
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `industria_ftp`;
CREATE TABLE `industria_ftp` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `ftp_pedidos` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ftp_retornos` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ftp_espelhos` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ftp_cancelados` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ftp_estoques` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fk_id_industria` int unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_industria_ftp_industria` (`fk_id_industria`),
  CONSTRAINT `fk_industria_ftp_industria` FOREIGN KEY (`fk_id_industria`) REFERENCES `industria` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Configuração FTP por indústria';

-- ---------------------------------------------------------------------
-- pedido
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `pedido`;
CREATE TABLE `pedido` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `numero_pedido_ol` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Chave natural — número do pedido no sistema da indústria',
  `id_industria` int unsigned DEFAULT NULL,
  `nome_arquivo` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codigo_interno_erp` int DEFAULT NULL COMMENT 'Código do pedido no ERP após importação',
  `cnpj_cliente` char(14) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `condicao` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '0',
  `data_pedido` datetime DEFAULT NULL,
  `valor_total` decimal(15,2) DEFAULT NULL,
  `status_operacional` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status_erp` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Pedidos recebidos via FTP. numero_pedido_ol é a chave de ligação com as demais tabelas.';

-- ---------------------------------------------------------------------
-- pedido_item
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `pedido_item`;
CREATE TABLE `pedido_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `numero_pedido_ol` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Referência ao pedido pelo número OL',
  `ean` varchar(14) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codigo_produto_erp` int DEFAULT NULL,
  `quantidade_solicitada` int DEFAULT NULL,
  `quantidade_atendida` int DEFAULT NULL,
  `preco` decimal(12,2) DEFAULT NULL,
  `desconto` decimal(5,2) DEFAULT NULL,
  `cod_motivo` int DEFAULT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_item_numero_pedido_ol` (`numero_pedido_ol`),
  KEY `idx_item_ean` (`ean`),
  CONSTRAINT `fk_item_pedido` FOREIGN KEY (`numero_pedido_ol`) REFERENCES `pedido` (`numero_pedido_ol`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Itens dos pedidos, ligados via numero_pedido_ol';

-- ---------------------------------------------------------------------
-- pedido_item_ocorrencia
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `pedido_item_ocorrencia`;
CREATE TABLE `pedido_item_ocorrencia` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `id_pedido_item` int unsigned DEFAULT NULL,
  `severidade` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codigo` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `descricao` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `resolvido` tinyint(1) DEFAULT '0',
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_item_ocorrencia_item` (`id_pedido_item`),
  KEY `idx_item_ocorrencia_severidade` (`severidade`),
  CONSTRAINT `fk_item_ocorrencia_item` FOREIGN KEY (`id_pedido_item`) REFERENCES `pedido_item` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Ocorrências de itens: produto sem estoque, EAN inválido, etc.';

-- ---------------------------------------------------------------------
-- pedido_historico
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `pedido_historico`;
CREATE TABLE `pedido_historico` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `numero_pedido_ol` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Referência ao pedido pelo número OL',
  `id_usuario` int unsigned DEFAULT NULL COMMENT 'NULL quando a ação for automática (serviço)',
  `acao` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `detalhe` text COLLATE utf8mb4_unicode_ci,
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_historico_numero_pedido_ol` (`numero_pedido_ol`),
  KEY `idx_historico_usuario` (`id_usuario`),
  KEY `idx_historico_acao` (`acao`),
  CONSTRAINT `fk_historico_pedido` FOREIGN KEY (`numero_pedido_ol`) REFERENCES `pedido` (`numero_pedido_ol`) ON DELETE CASCADE,
  CONSTRAINT `fk_historico_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `usuario` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Auditoria completa: login, reprocessamento, geração de arquivos, mudança de status';

-- ---------------------------------------------------------------------
-- pedido_ocorrencia
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `pedido_ocorrencia`;
CREATE TABLE `pedido_ocorrencia` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `numero_pedido_ol` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Referência ao pedido pelo número OL',
  `severidade` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codigo` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `descricao` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `resolvido` tinyint(1) DEFAULT '0',
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ocorrencia_numero_pedido_ol` (`numero_pedido_ol`),
  KEY `idx_ocorrencia_severidade` (`severidade`),
  CONSTRAINT `fk_ocorrencia_pedido` FOREIGN KEY (`numero_pedido_ol`) REFERENCES `pedido` (`numero_pedido_ol`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Ocorrências do pedido';

-- ---------------------------------------------------------------------
-- arquivo
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `arquivo`;
CREATE TABLE `arquivo` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `numero_pedido_ol` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Referência ao pedido pelo número OL',
  `nome` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hash_md5` char(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `caminho` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `situacao` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_arquivo_numero_pedido_ol` (`numero_pedido_ol`),
  KEY `idx_arquivo_tipo` (`tipo`),
  CONSTRAINT `fk_arquivo_pedido` FOREIGN KEY (`numero_pedido_ol`) REFERENCES `pedido` (`numero_pedido_ol`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Rastreabilidade de todos os arquivos: original, retorno, espelho, cancelamento';

-- ---------------------------------------------------------------------
-- erros
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `erros`;
CREATE TABLE `erros` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `descricao` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codigo_erp` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Erros possiveis para cada ocorrencia';

-- ---------------------------------------------------------------------
-- servico_monitorado
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `servico_monitorado`;
CREATE TABLE `servico_monitorado` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ultimo_heartbeat` datetime DEFAULT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mensagem` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `timeout_minutos` int DEFAULT '10',
  `criado_em` datetime DEFAULT CURRENT_TIMESTAMP,
  `atualizado_em` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_servico_nome` (`nome`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Monitoramento de heartbeat dos serviços Python';

SET FOREIGN_KEY_CHECKS = 1;

-- Seed minimo dos servicos monitorados (mesmo conteudo de OL_API/seed_servicos.sql)
INSERT INTO servico_monitorado (nome, status, mensagem, timeout_minutos, criado_em, atualizado_em)
VALUES
    ('importa_pedidos',           'Aguardando', 'Serviço não executou ainda', 15, NOW(), NOW()),
    ('coleta_pedidos_ftp_hypera', 'Aguardando', 'Serviço não executou ainda', 30, NOW(), NOW()),
    ('retornos',                  'Aguardando', 'Serviço não executou ainda', 15, NOW(), NOW()),
    ('espelhos',                  'Aguardando', 'Serviço não executou ainda', 15, NOW(), NOW()),
    ('envio_estoque',             'Aguardando', 'Serviço não executou ainda', 30, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    mensagem        = VALUES(mensagem),
    timeout_minutos = VALUES(timeout_minutos);
