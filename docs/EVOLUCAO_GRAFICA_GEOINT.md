# Evolução gráfica e GeoINT — Sentinel Atlas

Referência conceitual fornecida pelo mantenedor: God's Eye View (https://github.com/bilawalsidhu/gods-eye-view). Esta especificação descreve trabalho próprio; não incorpora código, imagens ou bases de terceiros sem conferência de suas licenças e atribuições.

## Interface
- [x] Painéis grafite foscos, botões discretos, foco visível e movimento reduzido.
- [x] Limpeza individual das camadas consultadas, sem excluir histórico GPS.
- [x] Origem, natureza, horário da observação e horário da consulta nos objetos GeoINT consultados.
- [ ] Validação visual em navegador real, em diferentes GPUs, resoluções e escalas.
- [ ] Rótulos cartográficos e limites territoriais licenciados, com nível de detalhe por zoom.
- [ ] Modelos 3D próprios/licenciados e orientação por curso válido; interpolação identificada como estimativa.
- [ ] Exploração cinematográfica em terceira pessoa e cabine renderizada, distinguindo simulação de câmera real.
- [ ] Modos visuais CRT, noturno, térmico ilustrativo (não apresentar filtro como medição de sensor).
- [ ] Ferramentas de desenho de áreas, linhas, pinos, importação e exportação de anotações locais.
- [ ] Timeline de dados observados, sem fabricar histórico ausente.

## Dados e camadas
| Recurso | Situação / próxima entrega |
|---|---|
| Globo base e relevo | Existente; preservar texturas e avaliar terreno multirresolução com licenças |
| Google 3D | Existente, depende de chave e faturamento; usar componente oficial |
| Esri / OSM / Cesium | Avaliar licenças, tokens e atribuições antes de integrar |
| Imagens recentes Sentinel-2 | Pendente: seleção de área e data, catálogo STAC, cobertura de nuvens, prévia e atribuição; acesso a pixels depende do provedor |
| Aeronaves | OpenSky existente; validar campos, idade do dado, limites e curso; sem prometer cobertura global |
| Satélites | CelesTrak e SGP4 existentes; ampliar categorias, rótulos de posição estimada e validade do TLE |
| Navios | GFW histórico existente; AIS ao vivo pendente, requer fonte autorizada |
| Trânsito | Google Maps existente; não copiar tiles nem dados brutos para outro motor; avaliar fluxo agregado/simulação rotulada |
| Transporte público | GeoJSON regional existente; avaliar GTFS/GTFS-RT e trilhas autorizadas |
| Meteorologia | Open-Meteo existente; radar, nuvens observadas, raios, ciclones e timeline pendentes |
| Terremotos / focos de calor / eventos | Integrações existentes; ajustar simbologia, idade dos eventos e fonte |
| Hidrologia, municípios, elevação e alertas | Catálogo existente; verificar cobertura e formato regional |
| Câmeras públicas | Pendente: apenas transmissões públicas autorizadas, sem reconhecimento facial nem rastreamento de pessoas; não inferir cobertura como medição |
| Rádio mundial | Pendente: catálogo de emissoras públicas autorizadas e reprodução por ação explícita |
| RF / SDR | Pendente: receptor próprio, espectro agregado e sinais autorizados; sem interceptação de comunicações privadas |
| Lançamentos espaciais | Pendente: calendário público, trajetórias ilustrativas rotuladas |
| Notícias e infraestrutura pública | Pendente: licenças, fontes e atribuições; avaliar finalidade, privacidade e nível de detalhe |
| Voz / copiloto | Pendente: sessão curta, consentimento do microfone e credenciais no servidor; somente ações verificáveis |
| MCP | Pendente: ferramentas de consulta restritas e anotações autorizadas, sem expor segredos |
| Instalação | Manter Python/FastAPI e Docker existentes; avaliar Codespaces e inicializador local |

## Requisitos de aceitação
- Separar observação, modelo, predição, histórico e demonstração. Mostrar indisponibilidade e idade da fonte.
- Consultas externas explícitas, com limites, cache conforme licença, timeouts e credenciais privadas no servidor.
- Não publicar chaves nem conteúdo de provedores sem permissão. Não abrir portas externas por padrão.
- Não desenvolver pesquisa de pessoas, reconhecimento facial ou interceptação de comunicação privada.
- Manter branches independentes, testes de regressão, CI e revisão antes de qualquer merge.
- O plano não significa que as integrações pendentes já estejam disponíveis. Dados ilustrativos não são adequados a decisões críticas.
