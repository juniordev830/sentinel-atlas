# VS Code: comandos e integração com GitHub

Este repositório inclui tarefas locais em `.vscode/tasks.json` e a configuração de workspace do GitHub MCP em `.vscode/mcp.json`.

## Usar os comandos Git

1. Abra a pasta deste repositório no VS Code.
2. Salve os arquivos abertos com **Ctrl+S**.
3. Pressione **Ctrl+Shift+P** e selecione **Tasks: Run Task**.
4. Escolha a tarefa desejada:
   - **Git: ver estado** — mostra alterações e branch atual.
   - **Git: atualizar do GitHub (pull --rebase)** — traz commits remotos antes de continuar; resolva conflitos, se houver.
   - **Git: adicionar alterações** — prepara as alterações para o commit.
   - **Git: criar commit** — solicita uma mensagem de commit.
   - **Git: enviar para GitHub (push)** — envia commits locais já criados.
   - **Git: salvar e enviar** — adiciona, cria o commit e tenta enviar ao GitHub em sequência.
5. Use também a tarefa de verificação do projeto, quando disponível, para executar testes ou validar o código.

**Importante:** a tarefa de envio não salva arquivos ainda não salvos no editor e não contorna autenticação, conflitos ou regras de proteção da branch. Se não houver alterações, o Git pode informar que nada há para commitar. Para reduzir conflitos, atualize do GitHub antes de começar a trabalhar.

## Usar o GitHub MCP

1. Use uma versão atual do VS Code que ofereça suporte a servidores MCP e ao modo Agent.
2. Abra **Ctrl+Shift+P → MCP: List Servers**.
3. Selecione o servidor **github** e inicie-o, se necessário.
4. Na primeira conexão, conclua o fluxo de autenticação/autorização do GitHub e aceite a confiança somente após revisar o servidor.
5. Verifique se o servidor está ativo e teste uma consulta no modo Agent.

A configuração usa o endpoint remoto oficial do GitHub e **não armazena token neste repositório**. A conexão MCP dá ao agente ferramentas para trabalhar com o GitHub de acordo com as permissões concedidas; revise as solicitações de acesso e as alterações antes de aceitá-las.

## Observações

- Git e GitHub são coisas diferentes: Git registra alterações localmente; `push` envia commits ao GitHub.
- Os comandos de execução/teste dependem da linguagem e das ferramentas instaladas na máquina.
- Projetos de documentação ou protótipos podem não ter uma tarefa de teste funcional.
