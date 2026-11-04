-- ============================================================================
-- Migração: parâmetro "limitador_de_envio"
--
-- Card: Reenvio de arquivos por período (tela de Histórico) / squad 2026-09-18
-- Executar manualmente no MySQL (painel_ol). A tabela `parametro` já existe
-- (ver migration_parametro.sql).
--
-- Para que serve: teto de pedidos por disparo do reenvio por período. O reenvio
-- é síncrono (FTP + cópia por arquivo), então um período largo derrubaria a
-- requisição no meio do lote e o operador ficaria sem saber o que já tinha
-- saído. Acima do teto a API recusa com 422 e pede para estreitar o período.
--
-- Enquanto esta linha não existir, a API cai no padrão de 250 (constante
-- _LIMITE_REENVIO_PADRAO em OL_API/app/routers/pedidos.py) e a tela de
-- Parametrização exibe um aviso em vez do campo — o PUT devolveria 404.
-- O valor é editável pela tela de Parametrização (Administrador / Gerente
-- Comercial), sem redeploy.
-- ============================================================================

-- Idempotente: reexecutar não sobrescreve um valor já ajustado pela tela.
INSERT INTO `parametro`
  (`chave`, `valor`, `descricao`)
VALUES
  ('limitador_de_envio', '250', 'Limita a quantidade maxima de envio de arquivos.')
ON DUPLICATE KEY UPDATE `chave` = `chave`;

-- Conferência
SELECT `chave`, `valor`, `descricao` FROM `parametro` WHERE `chave` = 'limitador_de_envio';
