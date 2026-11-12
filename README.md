# Sentinel Atlas

> Plataforma experimental de monitoramento geoespacial com geofencing, visualização 3D e uma API para ingestão e consulta de posições.

[![CI](https://github.com/juniordev830/sentinel-atlas/actions/workflows/ci.yml/badge.svg)](https://github.com/juniordev830/sentinel-atlas/actions/workflows/ci.yml)

O **Sentinel Atlas** reúne um núcleo de geolocalização em Python, uma API assíncrona com FastAPI e um painel web para explorar posições e camadas geográficas. O projeto pode ser executado em modo simulado, permitindo testar regras sem hardware GPS real.

> **Estado do projeto:** projeto em desenvolvimento. Algumas integrações dependem de chaves de API, serviços externos ou dependências opcionais. Consulte as seções abaixo antes de assumir que uma fonte está ativa.

## Visão geral

- **Geofencing:** cálculo de distância e detecção de entrada/saída de áreas configuradas.
- **API:** endpoints HTTP com FastAPI e canal WebSocket para posições.
- **Persistência local:** SQLite para geofences e posições GPS. A retenção limitada é **opt-in**; o sistema nunca exclui posições antigas apenas por inicializar ou atualizar o servidor.
- **Painel 3D:** interface web com camadas, filtros e rotas demonstrativas.
- **Fontes externas:** integrações opcionais com serviços públicos e provedores que exigem credenciais.
- **Execução reproduzível:** suporte a Docker e verificações automatizadas via GitHub Actions.

## Como usar o painel visual

No painel do **God's Eye View**, a área **Camadas** filtra os tipos de objetos e a área **Ferramentas** oferece controles do globo.

- **◫ Tela limpa / ▦ Mostrar painel:** ativa uma apresentação imersiva que esconde os painéis auxiliares sem bloquear o globo; o botão no topo ou a tecla `Esc` restauram os controles.
- **Visual tático:** uma moldura de comando com retículo, grade discreta e varredura visual opcional. Esses elementos são apenas decorativos, não indicam detecção de eventos e não interceptam cliques. A moldura desaparece no mapa 2D ou se o WebGL estiver indisponível.
- **Qualidade gráfica:** `Automático` usa Ultra em desktops com pelo menos 8 GB de memória e 8 núcleos informados pelo navegador, Equilibrado em outros desktops e Econômico em telas pequenas/dispositivos que solicitam movimento reduzido. `Ultra · 3D` libera geometria mais detalhada, suavização e até 2× de resolução física por pixel CSS, exigindo GPU e memória mais fortes. `Equilibrado` mantém boa fidelidade; `Econômico` reduz polígonos, resolução e desliga a nuvem 3D opcional. Os perfis podem ser trocados sem recarregar.
- **Terra renderizada:** textura diurna por padrão, modo noturno manual, relevo menos artificial, atmosfera com halo, reflexos oceânicos por máscara de água e iluminação solar estimada pelo horário UTC (aproximação astronômica). A posição do Sol é recalculada a cada minuto enquanto a aba está visível. **As nuvens são textura ilustrativa, não meteorologia observada ao vivo.**
- **⏸️ Pausar giro / ▶️ Retomar giro:** liga ou desliga a rotação automática; a rotação também é suspensa quando a aba fica oculta ou o usuário abre o mapa 2D. A preferência de acessibilidade por movimento reduzido é respeitada inicialmente e quando alterada.
- **🎯 Visão global:** fecha o inspetor, retorna do mapa 2D (se necessário) e recentraliza a câmera do globo.
- **Busca de objetos:** digite nomes ou identificadores; a busca considera a camada selecionada e continua aplicada quando a fonte de dados atualiza. Pressione `/` para focar a busca e `Esc` para limpá-la.
- **Geofences:** quando a API responde com uma lista vazia, o painel deixa de exibir geofences demonstrativas para evitar confusão com registros reais.

**Importante:** avião, navio, trânsito e parte dos satélites exibidos inicialmente são *dados simulados*. Camadas externas (como USGS) e outras integrações só devem ser consideradas atualizadas após respostas bem-sucedidas de suas respectivas fontes. A indicação de API online não significa que todos os provedores externos estejam operacionais.

## Google Maps 3D fotorrealista (visualizador oficial)

O Sentinel Atlas agora oferece **três experiências distintas**:
1. **Globo 3D independente**, com textura Blue Marble e luz solar estimada em UTC, sem Google Maps.
2. **Mapa satélite Google 2D**, com mapa híbrido, trânsito e busca manual no Google Places.
3. **🏙️ Google 3D**, visualização imersiva por meio da classe oficial `Map3DElement` da Maps JavaScript API (biblioteca `maps3d`, `mode: HYBRID`). O mapa inicia com a região apontada pelo globo (ou pelo mapa 2D, se ele estiver aberto) e permite explorar detalhes do relevo e de construções **onde houver cobertura**. Você pode voltar ao globo ou alternar para o mapa satélite.

**Como ativar:** habilite a Maps JavaScript API no Google Cloud, configure faturamento e chave restrita por HTTP referrers e por API, conforme as instruções abaixo. Com o backend rodando, clique em **Google 3D**. O componente só é criado após esse clique: não há pré-carregamento automático de imagens 3D. Para abrir com aceleração gráfica, habilite WebGL/aceleração de hardware no navegador.

**Licenciamento:** imagens e fotogrametria do Google são renderizadas somente pelo próprio componente Google Maps, com seus créditos e controles. Não copiamos tiles, imagens de satélite, prédios, nem dados brutos da plataforma para a textura do globo WebGL. Não armazenamos conteúdo do Google em cache próprio. A biblioteca 3D pode exigir recursos específicos do navegador, apresentar cobertura desigual ou gerar custos de **Immersive Maps**. Avalie cotas e alertas de faturamento no Google Cloud antes de disponibilizar publicamente.

Documentação: [Google Maps JavaScript API 3D](https://developers.google.com/maps/documentation/javascript/3d/overview) · [Map3DElement](https://developers.google.com/maps/documentation/javascript/reference/3d-map) · [Preço e faturamento](https://developers.google.com/maps/documentation/javascript/usage-and-billing).

## Melhorias visuais · renderização, navegação e meteorologia

### Terra mais natural
- **Noite urbana automática:** shader com textura noturna e máscara de incidência solar calculada; ilumina cidades no lado escuro do globo sem usar imagens/tiles do Google. O efeito é opcional e é desabilitado no perfil `Econômico` e ao selecionar manualmente a textura noturna.
- **Relevo e atmosfera calibrados:** intensidade do relevo e espessura do halo reduzidas para evitar montanhas e brilho artificiais. Os perfis `Ultra`, `Equilibrado` e `Econômico` continuam funcionando.
- **Nuvens:** camada decorativa carregada sob demanda, não uma estimativa de nuvens em tempo real. O modo Econômico não carrega essa camada.

### Navegação cinematográfica e Google 3D
- Na barra de ferramentas, selecione um **Destino** e clique em **✈ Sobrevoar**: Natal, Recife, Brasília, São Paulo ou Rio de Janeiro. O globo faz um movimento suave ou instantâneo caso o dispositivo prefira movimento reduzido.
- Depois do sobrevoo, clique em **🏙️ Google 3D** para abrir o componente fotorrealista oficial na região indicada, **se a chave estiver configurada**. Nesse modo aparecem botões para aproximar, afastar e girar a câmera. O alcance é limitado para evitar saltos exagerados.
- Ao alternar do mapa 3D do Google para o mapa 2D, a câmera tenta preservar o centro selecionado. Dados Google são renderizados unicamente em componentes oficiais, com suas atribuições e regras de uso. Movimentos no mapa 3D podem gerar novas requisições e custos de uso.

### Meteorologia e eventos naturais
- O botão **☁ Meteorologia** abre um painel lateral; nenhuma consulta é feita automaticamente.
- **Open-Meteo (modelo):** temperatura, umidade, vento, direção do vento, precipitação e cobertura de nuvens, quando retornados. Uma seta indica o sentido para o qual o vento sopra; a direção original fornecida pelo provedor indica de onde ele vem. Valores ausentes e inválidos não são exibidos como números.
- **Qualidade do ar (modelo):** PM2.5, PM10 e AQI (EUA), quando disponíveis.
- **NASA EONET:** até oito eventos catalogados listados no painel e marcadores com coordenadas retornadas pela API. **É um feed de eventos globais**, não uma varredura local ou alerta de emergência.
- **NASA FIRMS:** detecções térmicas somente quando `FIRMS_MAP_KEY` estiver configurada; não são incêndios confirmados.
- O painel informa a categoria do dado (modelo/evento/detecção), a fonte, timestamps disponíveis e se a resposta veio do cache. A visualização representa pontos consultados, **não** um radar meteorológico, campo vetorial regional ou mapa contínuo de temperatura.
- As camadas consultadas podem ser removidas com **Limpar dados**. Ao trocar a fonte ou se uma consulta falha, os marcadores antigos são removidos para evitar informações desatualizadas.
- Todas as chamadas continuam autenticadas pelo backend quando `SENTINEL_API_TOKEN` está configurado.

**Fontes e limites:** [Open-Meteo Forecast](https://open-meteo.com/en/docs), [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api), [NASA EONET](https://eonet.gsfc.nasa.gov/docs/v3), [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/). Use as fontes conforme termos e licenças; cobertura e latência variam.

## Google Maps e Places API (New)

O painel **God's Eye View** oferece um mapa 2D com imagens de satélite e nomes de vias (tipo híbrido), camada visual de trânsito do Google Maps, Street View (quando disponível) e buscas de estabelecimentos próximos.

**Como habilitar dados reais:**

1. Crie ou selecione um projeto no [Google Cloud Console](https://console.cloud.google.com/), vincule uma conta de faturamento e configure alertas/cotas de uso.
2. Ative **Maps JavaScript API**. Para buscar lugares próximos, ative também **Places API (New)**; usar o mapa sem buscas de lugares não requer fazer consultas Places.
3. Crie uma **chave de API para navegador**, restrita por **HTTP referrers** (domínios onde o painel será servido, como `http://localhost:8000/*` para testes locais) e pelas APIs necessárias. Nunca use o token administrativo do Sentinel Atlas como chave do Maps.
4. Configure somente no seu ambiente, nunca no GitHub:
   ```bash
   export GOOGLE_MAPS_API_KEY="sua-chave-restrita-ao-site"
   uvicorn backend.app:app --reload
   ```
   No Windows, use `$env:GOOGLE_MAPS_API_KEY="sua-chave-restrita-ao-site"` ou um arquivo `.env` local ignorado pelo Git.
5. Abra `http://localhost:8000`, clique em **Mapa satélite** e aguarde o mapa. Selecione uma categoria e clique em **Buscar nesta área** para uma consulta explícita, limitada aos **8 primeiros locais** em um raio de **1,5 km** do centro atual (sem atualização automática).

**O que é exibido:** mapa híbrido (satélite + rótulos), camada visual de trânsito, marcadores, nomes e endereços retornados por Google Places, com opção de abrir cada local no Google Maps. O botão **Limpar** remove os resultados temporários. O aplicativo **não** extrai velocidade do trânsito ou bases cartográficas brutas, nem armazena dados de Places em SQLite, arquivos ou localStorage.

**Regras importantes:**

- Os resultados Google Places são exibidos **somente no mapa oficial do Google**; não são copiados para o globo 3D de outro provedor. A interface deve preservar as atribuições e o logo do Google fornecidos pelo mapa.
- Uma chave da Maps JavaScript API **é visível ao navegador por definição**: proteja-a com restrições de site/API, limites de cota e monitoramento de custos. Não coloque chaves privadas de servidor em `/api/public-config`.
- Sem chave, permissões, faturamento ou conexão, o mapa do Google e o Places ficam indisponíveis; o globo demonstrativo, USGS e OSM são camadas independentes.
- A cobertura e a atualização do trânsito, do satélite, do Street View e dos locais variam por região; não são necessariamente em tempo real.
- Para distribuição pública, mantenha uma política de privacidade e termos de uso adequados às regras do Google Maps Platform.
- Consulte a [documentação oficial da Maps JavaScript API](https://developers.google.com/maps/documentation/javascript/get-api-key), [Nearby Search (New)](https://developers.google.com/maps/documentation/javascript/nearby-search) e as [políticas de atribuição do Places](https://developers.google.com/maps/documentation/places/web-service/policies).

## GeoINT: 16 categorias de fontes públicas

No painel web, clique em **🌐 Fontes GeoINT**. O catálogo lista 16 tipos de dados, indicando
**pronto para consulta**, **configuração necessária**, **visualização externa** ou **selecione uma UF**.
Uma consulta ocorre **somente quando você clica** em uma fonte; não existe coleta massiva
ou renovação automática com custo. A seleção de lugar usa as coordenadas do centro do globo.

| Categoria | Provedor | Implementação e condições |
|---|---|---|
| Imagens da Terra | NASA Worldview/GIBS | Abre o visualizador externo oficial; não oferece filmagem orbital ao vivo |
| Aeronaves | OpenSky | API de estados com recorte geográfico (±1°); pode limitar, bloquear ou não cobrir a área |
| Navios e portos | Global Fishing Watch | Eventos portuários históricos; requer `GFW_API_TOKEN` e respeitar uso não comercial |
| Focos de calor | NASA FIRMS | CSV VIIRS SNPP NRT por área (±1°), requer `FIRMS_MAP_KEY` e uso nos termos do serviço |
| Terremotos | USGS | GeoJSON de eventos do dia, atualizado periodicamente |
| Tempo | Open-Meteo | Consulta do modelo meteorológico atual; não é leitura de termômetro local |
| Eventos naturais | NASA EONET | Eventos abertos registrados, cobertura variável |
| Satélites orbitais | CelesTrak + SGP4 | Posição estimada da ISS a partir de elementos orbitais; não é observação física ao vivo |
| Edificações e POIs | OpenStreetMap/Overpass | Objetos mapeados em um raio de 700 m; cobertura comunitária e limites de acesso |
| Trânsito | Google Maps | Camada licenciada no mapa oficial; exige chave, não fornece dados brutos de veículos |
| Transporte público | Feed GeoJSON de operador regional | Exige `SENTINEL_TRANSIT_GEOJSON_URL`; não converte GTFS-Realtime protobuf automaticamente |
| Hidrologia | Feed GeoJSON oficial/regional, como dados ANA | Exige `SENTINEL_HYDRO_GEOJSON_URL` |
| Qualidade do ar | Open-Meteo | Indicadores PM2.5, PM10 e AQI **modelados**, não dados de sensores locais |
| Municípios do Brasil | IBGE | Selecione uma UF, veja nomes e códigos oficiais; o cadastro não traz coordenadas individuais |
| Elevação | Copernicus DEM via Open-Meteo | Altitude modelada em metros (resolução aproximada de 90 m) |
| Alertas públicos | Feed GeoJSON governamental regional | Exige `SENTINEL_ALERTS_GEOJSON_URL` e licença compatível |

As 16 categorias estão **presentes no painel e na API**, mas isso **não significa que todas
já estejam fornecendo posições ao vivo**. Fontes opcionais e regionais continuam desativadas
até que credenciais ou endpoints legítimos sejam configurados.

**Rotas (autenticadas quando SENTINEL_API_TOKEN está configurado):**

```http
GET /api/geoint/layers
GET /api/geoint/layers/weather?lat=-5.79&lng=-35.21
GET /api/geoint/layers/earthquakes?lat=-5.79&lng=-35.21
GET /api/geoint/layers/municipalities?lat=-5.79&lng=-35.21&uf=RN
```

Os retornos incluem `provider`, `status`, `data_kind`, `items`, `count`,
`fetched_at`, `cached` quando aplicável, e `requirement` quando a configuração falta.
As falhas são apresentadas como indisponíveis, nunca preenchidas com pontos fictícios.
Os pontos reais têm identificadores com `type=geoint-<fonte>` e podem ser filtrados,
diferentemente dos marcadores de demonstração existentes.

**Configuração local opcional (não comite segredos):**

```dotenv
FIRMS_MAP_KEY=
GFW_API_TOKEN=
SENTINEL_TRANSIT_GEOJSON_URL=
SENTINEL_HYDRO_GEOJSON_URL=
SENTINEL_ALERTS_GEOJSON_URL=
```

Os URLs regionais devem ser endereços HTTPS configurados pelo operador da instalação,
de fontes autorizadas a publicar GeoJSON `FeatureCollection` com geometria `Point`
e propriedades como `name`, `description` e `time`. Formatos GTFS, CSV hidrológico
e alertas CAP/XML precisam ser convertidos por um conector próprio antes dessa integração.

**Desempenho e privacidade:** respostas são limitadas a 1,5 MB, com até 75 itens
por consulta (menor em algumas fontes), timeout de oito segundos e cache de memória
de cinco minutos. Não existe armazenamento persistente de fontes terceiras ou
captura silenciosa da geolocalização do visitante. A posição usada nas consultas é
a câmera do globo, não a posição GPS do aparelho.

**Atribuições e direitos:** os dados têm licenças, cotas e regras distintas. Open-Meteo
requer atribuição ao provedor e bases associadas; cartografia OSM requer crédito
© OpenStreetMap contributors. Global Fishing Watch exige token e uso não comercial.
Google Maps/Places permanece no mapa oficial licenciado. Avalie os termos individuais
antes de comercializar ou redistribuir dados.

## Arquitetura

| Componente | Responsabilidade |
|---|---|
| `python/gps_core.py` | Cálculo de distância, leitura de coordenadas, geofencing e modo de demonstração |
| `python/settings.py` | Carregamento de configurações do ambiente |
| `backend/app.py` | API FastAPI, health check, fontes, geofences e WebSocket |
| `backend/storage.py` | Persistência SQLite das geofences |
| `typescript/gps_client.ts` | Cliente TypeScript para envio de posições |
| `web/index.html` | Painel web 3D e controles de visualização |
| `tests/test_gps.py` | Testes do núcleo geográfico e das transições de geofence |
| `Dockerfile`, `compose.yaml`, `.dockerignore` | Contêiner local com autenticação obrigatória e segredos excluídos do build |
| `.github/workflows/ci.yml` | Verificações automatizadas |

## Requisitos

- Python 3.10 ou superior (recomenda-se uma versão suportada pelo ambiente de dependências).
- Git.
- Docker e Docker Compose, se preferir executar em contêiner.
- Chaves de API apenas para os provedores que as exigem.

## Executar localmente

### 1. Clonar o repositório

```bash
git clone https://github.com/juniordev830/sentinel-atlas.git
cd sentinel-atlas
```

### 2. Criar e ativar o ambiente virtual

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependências

```bash
pip install -r backend/requirements.txt
```

### 4. Iniciar a API

```bash
uvicorn backend.app:app --reload
```

A API fica disponível em `http://localhost:8000`. O painel web pode ser aberto em `http://localhost:8000` quando servido pela aplicação, ou diretamente em `web/index.html` para a experiência estática.

Verifique a API com:

```bash
curl http://localhost:8000/api/health
```

### Alternativa: Docker Compose (seguro por padrão)

O `compose.yaml` agora existe no repositório. Antes de iniciar, configure
um token **aleatório com pelo menos 32 caracteres**, somente no seu ambiente:

Linux/macOS:

```bash
export SENTINEL_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker compose up --build
```

Windows PowerShell:

```powershell
$env:SENTINEL_API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

- Acesse **somente no próprio computador**: `http://127.0.0.1:8000/login`.
  Informe o token gerado na tela de login; não o salve no código ou no Git.
- O Compose exige `SENTINEL_ENV=production` e recusa iniciar sem a variável
  `SENTINEL_API_TOKEN`. Mesmo com token definido, o servidor rejeita
  senhas curtas na inicialização.
- O mapeamento de porta é `127.0.0.1:8000:8000` (não acessível pela rede
  local). A escuta em `0.0.0.0` no Dockerfile é **somente dentro do contêiner**.
- O SQLite fica em um volume Docker chamado `atlas-data`, mantido entre
  reinicializações. `docker compose down -v` **apaga esse volume e os dados**;
  não use `-v` sem intenção de excluir o histórico.
- O `.dockerignore` exclui `.env`, bancos locais, caches e arquivos de Git
  do contexto da imagem. O processo roda como usuário não privilegiado.
- Para acesso remoto, configure HTTPS, autenticação e um proxy seguro:
  **não altere o binding para `0.0.0.0` sem revisar a exposição de GPS,
  controles de acesso, limites de tentativas e isolamento por usuário**.

Para interromper sem apagar os dados, rode `docker compose down`.

## Executar o núcleo de geofencing

Demonstração em torno de uma coordenada de referência:

```bash
python python/gps_core.py --demo --center-lat -23.5505 --center-lon -46.6333
```

Testar uma posição e um raio:

```bash
python python/gps_core.py --lat -23.5505 --lon -46.6333 --center-lat -23.5505 --center-lon -46.6333 --radius 250
```

Converter uma sentença NMEA GPRMC:

```bash
python python/gps_core.py --nmea '$GPRMC,123519,A,2331.000,S,04637.998,W,0.0,0.0,230326,,,A*00' --center-lat -23.5167 --center-lon -46.6333
```

## Endpoints principais

| Método/canal | Endpoint | Objetivo |
|---|---|---|
| GET | `/api/health` | Verificar disponibilidade da API |
| GET | `/api/sources` | Consultar fontes configuradas |
| GET / POST | `/api/geofences` | Consultar e cadastrar geofences |
| WebSocket | `/ws/positions` | Canal de posições em tempo real |
| GET | `/api/map/features?lat=-5.8&lng=-35.2&radius=500` | Consultar edifícios, vias, transporte e locais mapeados pelo OpenStreetMap em um raio de até 1,5 km |

Os endpoints disponíveis podem evoluir durante o desenvolvimento. Consulte `backend/app.py` para o contrato atual.

## Configuração e integrações

1. Copie `.env.example` para `.env`, caso o arquivo de exemplo esteja presente.
2. Preencha apenas as credenciais dos provedores que deseja habilitar.
3. Mantenha segredos e tokens no ambiente local; nunca os envie ao Git.

O projeto prevê integrações opcionais com fontes como NASA GIBS, USGS Earthquakes, CelesTrak/SGP4, OpenStreetMap/Overpass (edifícios, vias, transporte e locais mapeados) e provedores que exigem credenciais, como Google Maps, Copernicus, AISStream e OpenSky. A disponibilidade depende da configuração local, de limites dos serviços e das dependências instaladas.

## Testes

Execute os testes automatizados do núcleo geográfico:

```bash
pytest
```

Se algum comando falhar, confira as dependências instaladas e a configuração do ambiente antes de concluir que o serviço está indisponível.

## Segurança e privacidade

- Coordenadas GPS podem revelar a localização de uma pessoa. Use dados simulados durante desenvolvimento e testes.
- Não registre nem publique coordenadas reais sem necessidade e autorização.
- Nunca versione arquivos `.env`, tokens, chaves ou dados pessoais.
- Proteja a API com autenticação e controles de acesso adequados antes de expô-la à internet. O Compose padrão não publica portas fora do host local e exige token forte.
- Restrinja chaves de provedores por domínio e permissões sempre que o serviço oferecer essa opção.

## Retenção de posições GPS (opt-in, com backup obrigatório)

Por padrão, **não há exclusão automática** de posições armazenadas. Para limitar
o histórico, configure a variável de ambiente
`SENTINEL_POSITION_RETENTION_LIMIT=10000` (inteiro de 1 a 1.000.000)
**antes de iniciar o processo**. Use uma variável do sistema ou configuração
do contêiner; não publique tokens ou dados GPS no Git.

**Atenção:** esta opção exclui permanentemente posições antigas **depois da
próxima gravação de GPS**, conservando os registros mais recentes na quantidade
configurada. O simples início do servidor não exclui nada. Faça um backup
verificado do banco SQLite, inclusive dos volumes Docker, antes de habilitar
a retenção. Sem um backup, não há como recuperar as posições descartadas.

O Compose fornecido não define o limite de retenção e, portanto, preserva
os dados existentes por padrão. O histórico de posições é sensível; uma
retenção por quantidade não substitui política de privacidade por período.

## Próximos passos sugeridos

- Expandir a cobertura de testes unitários e de integração.
- Documentar schemas de requisição e resposta de cada endpoint.
- Validar autenticação, autorização, limites de requisição e tratamento de erros.
- Adicionar observabilidade estruturada e métricas operacionais.
- Separar claramente dados simulados e dados reais na interface.

## Tecnologias

**Python · FastAPI · SQLite · TypeScript · JavaScript · HTML/CSS · WebSocket · Docker · GitHub Actions**

## Autor

**João Junior** — estudante de Engenharia de Software, desenvolvendo projetos práticos em backend, APIs e aplicações web.

- GitHub: https://github.com/juniordev830

---

Este repositório é um projeto de portfólio em evolução. Recursos e integrações devem ser avaliados conforme o código e a configuração disponíveis na versão atual.


## Segurança para produção

A API exige `SENTINEL_API_TOKEN` com pelo menos 32 caracteres quando `SENTINEL_ENV=production`; a aplicação falha na inicialização se essa configuração estiver ausente ou fraca. Use um segredo aleatório guardado no gerenciador de segredos do ambiente, nunca versionado no Git.

- As rotas `/api/health` e `/api/public-config` são públicas intencionais.
- Clientes de serviço podem autenticar com `Authorization: Bearer <token>`.
- Para usar o painel no navegador, abra `/login` e informe o token administrativo. O servidor troca o token por um cookie de sessão assinado, `HttpOnly`, `SameSite=Strict` e com validade de uma hora; em produção, o cookie também usa `Secure`.
- O token não é salvo em `localStorage`, não é inserido no JavaScript do painel e não é enviado na URL. O cookie é enviado automaticamente pelo navegador nas chamadas HTTP e WebSocket da mesma origem.
- Requisições mutáveis autenticadas por cookie e a conexão WebSocket validam a origem. Mantenha HTTPS em produção.
- O token administrativo continua sendo uma credencial compartilhada: esta sessão de navegador não implementa contas individuais, papéis ou isolamento de dados por usuário. Não exponha o serviço multiusuário antes de implementar autorização por tenant/objeto e limitação de tentativas no proxy de borda.

## Validação e manutenção

Para revisar alterações neste projeto, consulte o [guia técnico de validação](docs/GUIA_DE_VALIDACAO.md), com comandos, cenários de regressão e próximos incrementos.
