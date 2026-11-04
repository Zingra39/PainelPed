-- ============================================================================
-- Migração: tabela `parametro` + parâmetro "transmissao_automatica_pronto"
--           + usuário "Sistema" (usado no histórico para ações automáticas)
--
-- Card: Tela de Parametrização — Task #40 / squad review 2026-09-17
-- Executar manualmente no MySQL de produção (painel_ol). Rodar tudo em uma
-- única transação evita ficar com metade da migração aplicada em caso de erro.
-- ============================================================================

START TRANSACTION;

-- ------------------------------------------------------------------
-- 1) Tabela genérica de parâmetros de configuração do sistema
-- ------------------------------------------------------------------
CREATE TABLE `parametro` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `chave` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Identificador único usado pelo código (ex: transmissao_automatica_pronto)',
  `valor` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Valor atual do parâmetro (ex: "1"/"0" para os booleanos de hoje)',
  `descricao` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Texto exibido na tela de parametrização',
  `id_usuario_atualizacao` int unsigned DEFAULT NULL COMMENT 'Último usuário que alterou o valor',
  `atualizado_em` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_parametro_chave` (`chave`),
  KEY `fk_parametro_usuario` (`id_usuario_atualizacao`),
  CONSTRAINT `fk_parametro_usuario` FOREIGN KEY (`id_usuario_atualizacao`) REFERENCES `usuario` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Parâmetros de configuração do sistema, editáveis pela tela de parametrização';

-- ------------------------------------------------------------------
-- 2) Seed do parâmetro desta etapa — nasce DESLIGADO por padrão ('0'),
--    ou seja, comportamento atual (fila de triagem) não muda até alguém
--    ligar explicitamente na tela.
-- ------------------------------------------------------------------
INSERT INTO `parametro` (`chave`, `valor`, `descricao`) VALUES
  ('transmissao_automatica_pronto', '0',
   'Ao ligar, pedidos que atingem "Pronto" na triagem são transmitidos automaticamente para a pasta de entrada, sem ação humana.');

-- ------------------------------------------------------------------
-- 3) Usuário "Sistema" — referenciado como id_usuario em pedido_historico
--    quando a transmissão for automática (parâmetro ligado).
--    ativo=0 e senha_hash NULL: nunca consegue logar (ativo=0 já bloqueia
--    acesso ao painel hoje, conforme confirmado pelo time).
-- ------------------------------------------------------------------
INSERT INTO `usuario` (`nome`, `email`, `senha_hash`, `id_perfil`, `ativo`) VALUES
  ('Sistema', 'sistema@painelol.local', NULL, NULL, 0);

COMMIT;

-- ------------------------------------------------------------------
-- Verificação pós-migração (rodar manualmente e conferir o resultado):
--   SELECT * FROM parametro WHERE chave = 'transmissao_automatica_pronto';
--   SELECT * FROM usuario WHERE nome = 'Sistema';
-- ------------------------------------------------------------------
