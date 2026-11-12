# Plano de validação — Sentinel Atlas

O repositório combina serviços Python em `backend/`, módulos geográficos em `data/`, frontend em `web/` e arquivos de infraestrutura Docker. As origens de camadas e suas condições estão inventariadas em `DATA_SOURCES.md`.

## Preparar um ambiente de teste

- Consultar `README.md` e `.env.example` antes de executar as etapas locais ou via `docker-compose.yml`.
- Validar a API em modo simulado, sem depender inicialmente de tokens ou provedores externos.
- Conferir `/api/health` e abrir a experiência web com a API correta; não inferir saúde de um serviço apenas porque a página carregou.
- Confirmar que camadas opcionais identificam fonte, atualização e estado de indisponibilidade.
- Verificar latência e volume de dados em consultas geográficas, filtros, WebSockets e integração de camadas.

## Cenários críticos

1. Geofencing com posições nas bordas e cruzamento de limites.
2. Coordenadas fora do intervalo, precisão desconhecida e informação temporal ausente.
3. Reconexão ao WebSocket e supressão de eventos repetidos.
4. Falha de fonte externa: a interface não deve apresentar dado antigo como tempo real.
5. Renderização 3D em dispositivo sem GPU adequada, viewport pequeno e rede lenta.
6. Proteção de chaves e credenciais, respeito aos termos de uso das fontes e privacidade de localizações.

## Próxima etapa

Registrar comandos de benchmark, fixtures mínimos e testes E2E com reprodução determinística de fontes. Não promover como sistema de vigilância operacional sem uma avaliação específica de confiabilidade, privacidade e permissões.
