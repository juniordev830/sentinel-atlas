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
| `Dockerfile`, `docker-compose.yml` | Empacotamento e execução local |
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

### Alternativa: Docker

```bash
docker compose up --build
```

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
- Proteja a API com autenticação e controles de acesso adequados antes de expô-la à internet.
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
