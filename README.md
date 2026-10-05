# Atividade ponderada M7 - Predição de Bitcoin com Docker

&emsp;Nessa atividade eu montei uma solução com dois containers: um que treina um modelo pra estimar o fechamento do Bitcoin do dia seguinte, e outro que carrega esse modelo e responde pedidos de predição por uma API em Python.

&emsp;OBS: a predição não é recomendação de investimento e nem dá pra confiar nela de verdade.

## Estrutura de pastas

```
ponderada-m7-moeda/
├── README.md             
├── docker-compose.yml     <- sobe treino + backend juntos
├── data/
│   ├── baixar_btc.py      <- script que baixa o histórico
│   └── btc_usd.csv        <- dados (date, close, volume)
├── training/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── train.py           <- treina e salva o modelo
├── models/                <- onde o modelo treinado é salvo (volume compartilhado)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py             <- API FastAPI (/health e /predict)
└── client/
    └── cliente.py         <- aplicação cliente que chama o backend
```

## Entendimento da solução

&emsp;A solução foi construída separando o sistema em duas partes: **treinamento** e **inferência**. O treinamento pega os dados históricos e gera o modelo. A inferência usa esse modelo pronto para fazer previsões quando recebe uma requisição.

&emsp;Separei essas duas partes porque elas funcionam de formas diferentes. O treinamento não precisa ficar rodando o tempo todo. Ele executa o código, gera o modelo e pode ser encerrado. Já o backend precisa continuar ativo esperando novas requisições. Por isso usei dois containers, um para o `train.py` e outro para a API em FastAPI.

### Fluxo de treinamento

&emsp;O treinamento começa quando o container executa o `train.py`. O script lê o CSV disponível em `/data` e prepara os exemplos que serão usados pelos modelos.

&emsp;Cada exemplo é formado pelos fechamentos de **7 dias consecutivos**. O fechamento do dia seguinte é usado como o valor que o modelo precisa aprender a estimar. Eu não passo os preços absolutos diretamente para o modelo. Os 7 valores da janela são divididos pelo último preço dela. O último valor da janela passa a ser `1` e os outros representam a relação deles com esse preço. O valor que quero prever também é transformado nessa mesma lógica, dividindo o preço do dia seguinte pelo último preço conhecido.

&emsp;Isso faz com que o modelo trabalhe mais com a variação dos preços dentro da janela do que com o valor absoluto do Bitcoin. Por exemplo, uma janela com preços perto de 60 mil e outra com preços perto de 80 mil podem ser representadas de forma parecida se o comportamento dos preços tiver sido parecido.

&emsp;Depois disso, separo os exemplos em treino e teste seguindo a ordem das datas. Os 80% mais antigos ficam no treino e os 20% mais recentes ficam no teste. Essa parte é importante porque não faria sentido misturar datas antigas e futuras em uma série temporal.

&emsp;Para ter uma referência antes dos modelos, também calculo um **baseline**. Nesse caso, a previsão é simplesmente considerar que o preço do próximo dia será igual ao último preço conhecido. Assim consigo comparar os modelos de machine learning com uma estratégia bem simples.

&emsp;Eu quis comparar um modelo mais simples e linear, que foi o Ridge, com um modelo capaz de capturar relações não lineares, que foi o Random Forest. Além deles, coloquei o baseline para ter uma referência simples.

&emsp;Nos testes, o Ridge teve MAE de **1323,11 USD** e o Random Forest teve **1352,42 USD**. O Ridge foi o melhor entre os dois modelos de machine learning. Só que o baseline teve MAE de **1305,76 USD**, então ele ainda foi melhor que os dois modelos. Isso mostra que, com os dados e a configuração que usei, o modelo não conseguiu superar uma previsão bem simples.

&emsp;Mesmo assim, depois da comparação escolho o melhor modelo de machine learning e treino ele novamente usando todos os exemplos disponíveis. No meu caso, o escolhido foi o Ridge. O modelo final é salvo em `modelo_btc.joblib`.

&emsp;Também salvo um `metadata.json` com informações usadas pela aplicação de inferência, como o modelo escolhido e o tamanho da janela. Assim o backend consegue saber como o artefato foi preparado.

### Fluxo de disponibilização do modelo

&emsp;Depois que o treinamento termina, o modelo precisa ficar disponível para o backend. Para fazer isso, usei a pasta `./models` como um volume compartilhado entre os dois containers.

&emsp;O container de treinamento monta essa pasta em `/models` e grava nela o `modelo_btc.joblib` e o `metadata.json`. O backend monta a mesma pasta, mas em modo somente leitura.

&emsp;Com isso, não precisei colocar o modelo dentro da imagem do backend. O modelo é um arquivo gerado pelo treinamento, então faz mais sentido deixar ele como um artefato separado. Se eu executar o treinamento novamente e gerar outro modelo, o backend pode carregar esse novo arquivo pelo mesmo volume.

### Fluxo de inferência

&emsp;Quando o backend inicia, ele procura o `modelo_btc.joblib` dentro de `/models`. Se encontrar o arquivo, carrega o modelo com `joblib` e deixa ele em memória enquanto a API estiver rodando. Assim não preciso abrir e carregar o arquivo toda vez que alguém faz uma previsão.

&emsp;A API tem dois endpoints principais. O `/health` serve para verificar se o backend está funcionando e se o modelo foi carregado. O `/predict` recebe os dados para fazer uma previsão.

&emsp;No `/predict`, envio exatamente **7 preços de fechamento**. O backend também verifica se os valores recebidos são válidos. Depois aplica a mesma transformação usada no treinamento, dividindo os valores pelo último fechamento da janela.

&emsp;O modelo recebe esses valores transformados e executa o `modelo.predict()`. Como o modelo foi treinado para prever uma relação com o último preço, o backend transforma o resultado de volta para um valor em dólar.

&emsp;A resposta da API mostra o último fechamento enviado, a previsão do próximo fechamento, a variação percentual prevista, o modelo utilizado e um aviso de que a previsão é experimental.

### Fluxo completo

&emsp;Quando executo `docker compose up`, o Compose inicia primeiro o container de treinamento. Ele lê os dados, prepara os exemplos, compara os modelos e salva os arquivos na pasta compartilhada.

&emsp;O backend depende do término bem sucedido desse treinamento. Para isso usei `depends_on` com `service_completed_successfully`. Então o backend só começa depois que o container de treinamento termina sem erro.

&emsp;Depois disso, o backend carrega o modelo salvo e começa a aceitar requisições na porta 8000. O cliente pode chamar o `/health` para verificar o serviço ou o `/predict` para enviar os 7 fechamentos e receber a previsão.

&emsp;No final, o caminho que montei foi: **dados históricos → treinamento → modelo treinado → volume compartilhado → backend → requisição → previsão**. Cada container fica responsável por uma parte diferente da aplicação.

## Diagramas

### Diagrama de componentes

&emsp;O primeiro diagrama mostra quais são as partes da aplicação e como elas estão conectadas. O arquivo CSV é a entrada do treinamento. O `train.py` roda dentro do primeiro container e grava os artefatos na pasta `./models`.

&emsp;Essa pasta é compartilhada com o segundo container. O backend lê o modelo dela quando inicia. A aplicação cliente fica fora dos containers de treinamento e backend e se comunica com a API usando HTTP.

```mermaid
flowchart LR

    CSV[("data/btc_usd.csv<br/>date, close, volume")]

    subgraph T["Container 1: treino"]
        TR["train.py<br/>scikit-learn"]
    end

    VOL[/"Volume compartilhado ./models<br/>modelo_btc.joblib<br/>metadata.json"/]

    subgraph B["Container 2: backend"]
        API["app.py<br/>FastAPI :8000<br/>GET /health<br/>POST /predict"]
    end

    CL["Aplicação cliente<br/>client/cliente.py ou curl"]

    CSV -->|"dados históricos"| TR
    TR -->|"salva artefatos"| VOL
    VOL -->|"backend carrega o modelo"| API
    CL -->|"HTTP POST /predict<br/>7 fechamentos"| API
    API -->|"JSON com previsão"| CL
```

&emsp;A parte mais importante desse diagrama é o **volume compartilhado**. Ele é o meio usado para passar o resultado do treinamento para o backend. O container de treino escreve nele e o backend só lê.

### Diagrama de sequência

&emsp;O segundo diagrama mostra a ordem em que as coisas acontecem. Diferente do primeiro, aqui o foco não é mostrar só os componentes, mas o que acontece primeiro e o que acontece depois durante a execução.

```mermaid
sequenceDiagram

    actor U as Eu (terminal)
    participant C as docker compose
    participant T as Container treino
    participant V as Volume ./models
    participant B as Container backend
    participant K as Cliente

    U->>C: docker compose up --build
    C->>T: inicia o treinamento
    T->>T: lê CSV e prepara os dados
    T->>T: treina e compara os modelos
    T->>V: salva modelo_btc.joblib e metadata.json
    T-->>C: termina com sucesso
    C->>B: inicia o backend
    B->>V: carrega o modelo
    U->>B: GET /health
    B-->>U: status ok + modelo carregado
    K->>B: POST /predict
    B->>B: valida os 7 fechamentos
    B->>B: transforma os dados
    B->>B: executa modelo.predict()
    B-->>K: retorna a previsão
```

&emsp;Nesse fluxo, o backend não começa junto com o treinamento. Primeiro o modelo precisa ser gerado e salvo. Depois o Compose inicia o backend, que carrega esse arquivo. Só então o cliente consegue fazer as requisições de previsão.

&emsp;Também da pra ver no diagrama que a previsão não volta para o container de treinamento. Depois que o modelo foi gerado, quem responde as requisições é somente o backend.

## Os dados

&emsp;Usei o histórico diário de **BTC-USD** do Yahoo Finance, de 2020-01-01 até o dia 2026-10-05. O CSV tem três colunas: `date`, `close` (preço de fechamento) e `volume`.

&emsp;Baixei com o script `data/baixar_btc.py` (usa a biblioteca `yfinance`) e salvei como CSV dentro do repositório. Fiz isso pra ganhar tempo e pra o treino não depender de internet: o container de treino só lê o arquivo, não precisa baixar nada.

&emsp;Pra gerar de novo:

```bash
pip install yfinance pandas

python data/baixar_btc.py
```

&emsp;**A tarefa de previsão:** dado os fechamentos dos últimos 7 dias, estimar o fechamento do dia seguinte.

&emsp;**Treino e teste:** como é série temporal, separei de forma cronológica: os primeiros 80% dos dias treinam e os 20% mais recentes testam. Não embaralhei nada, senão o modelo "veria o futuro" no treino.

## Devlog

### Etapa 1 - Entender o desafio e desenhar a arquitetura 

&emsp;**O que eu fiz:** li o enunciado e separei o que era obrigatório: treino em Docker ou notebook, um segundo container com backend em Python, uma rota de predição e uma forma de checar se o serviço está vivo.

&emsp;**Decisões:**
- **Dois containers separados** (treino e backend). O treino roda e termina; o backend fica de pé. Faz sentido porque são ciclos de vida diferentes.
- **Volume compartilhado `./models`** pra passar o modelo de um container pro outro. Considerei copiar o modelo pra dentro da imagem do backend, mas aí cada novo treino exigiria rebuild da imagem.
- **FastAPI** no backend, porque valida a entrada sozinho e gera a página `/docs`.
- **Previsão:** fechamento do dia seguinte, olhando os 7 últimos dias.

&emsp;**Evidência:** diagrama UML em [`README.md`](README.md).

&emsp;**Uso de IA:** pedi ajuda pra IA pra organizar a estrutura de pastas e montar o mermaid do diagrama. Eu revisei pra ver se estava batendo com o que eu tinha pensado (principalmente a parte do volume).

### Etapa 2 - Dados

&emsp;**O que eu fiz:** baixei o histórico diário de BTC-USD do Yahoo Finance com o `data/baixar_btc.py` e salvei em `data/btc_usd.csv`.

&emsp;**Decisões:** guardei o CSV no repositório pra o treino não depender de internet e pra qualquer pessoa conseguir reproduzir com os mesmos dados.

&emsp;**Teste:** conferi o arquivo depois de baixar:

```bash
head -5 data/btc_usd.csv
date,close,volume
2020-01-01,7200.17431640625,18565664997
2020-01-02,6985.47021484375,20802083465
2020-01-03,7344.88427734375,28111481032
2020-01-04,7410.65673828125,18444271275
```

```bash
wc -l data/btc_usd.csv
2471 data/btc_usd.csv
```

&emsp;**Dificuldade:** Nessa etapa, gerar o csv não me gerou dúvidas

&emsp;**Uso de IA:** a IA escreveu o script de download pra ganhar tempo. O que eu entendi: ele baixa preço diário, fica só com data, fechamento e volume, e salva em CSV.

### Etapa 3 - Treino e exportação do modelo

&emsp;**O que eu fiz:** escrevi/revisei o `training/train.py`, o `requirements.txt` e o `Dockerfile` responsável pelo ambiente de treinamento. A ideia foi deixar o treinamento reproduzível dentro de um container Docker, lendo os dados da pasta `data/` e salvando o modelo treinado na pasta `models/`.

&emsp;**Decisões:**

* Janela de 7 dias, dividida pelo último preço. Dessa forma, o modelo aprende a variação do preço em relação ao valor mais recente, em vez de trabalhar diretamente com o valor absoluto do dólar.
* Split cronológico 80/20, sem embaralhar os dados. Como se trata de uma série temporal, mantive a ordem dos acontecimentos para evitar que dados do futuro fossem usados no treinamento de forma indevida.
* Dois modelos foram comparados: Ridge e Random Forest.
* Também foi utilizado o baseline "amanhã = hoje", que serve como uma referência simples para verificar se os modelos realmente conseguem melhorar uma previsão muito básica.
* O modelo escolhido foi salvo em formato `joblib`, adequado para modelos do scikit-learn.
* Também foi definido o salvamento de um `metadata.json`, contendo informações como a janela utilizada e as métricas, para que o backend saiba como utilizar o artefato posteriormente.

&emsp;**Primeira tentativa de execução:**

&emsp;Inicialmente tentei executar o treinamento pelo Git Bash:

```bash
docker run --rm \
  -v "$(pwd)/data:/data:ro" \
  -v "$(pwd)/models:/models" \
  treino-btc
```

&emsp;O container iniciou, mas o treinamento apresentou:

```text
Traceback (most recent call last):
  File "/app/train.py", line 93, in <module>
    main()
  File "/app/train.py", line 41, in main
    df = pd.read_csv(DATA_PATH, parse_dates=["date"]).sort_values("date")
...
FileNotFoundError: [Errno 2] No such file or directory: '/data/btc_usd.csv'
```

&emsp;A primeira interpretação foi que o arquivo CSV não existia ou não estava sendo montado corretamente dentro do container. Verifiquei a pasta `data/` diretamente no terminal:

```bash
ls data/
```

&emsp;A saída foi:

```text
baixar_btc.py
btc_usd.csv
```

&emsp;Ou seja, o arquivo existia no meu computador e estava com o nome correto. Isso indicou que o problema não estava no dataset, mas na forma como o diretório estava sendo montado no container.

&emsp;Também percebi que haviam surgido pastas com nomes estranhos, como `data;C` e `models;C`. Isso indicava um problema na interpretação dos caminhos do Windows pelo Git Bash ao utilizar `$(pwd)` nos volumes do Docker.

&emsp;**Tentativa de corrigir o caminho pelo Git Bash:**

&emsp;Tentei passar os caminhos do Windows explicitamente:

```bash
docker run --rm \
  -v "C:/Users/Isabel/OneDrive/Documentos/Inteli/2026/M07/ponderada-m7-moeda/data:/data:ro" \
  -v "C:/Users/Isabel/OneDrive/Documentos/Inteli/2026/M07/ponderada-m7-moeda/models:/models" \
  treino-btc
```

&emsp;Nesse caso, o Docker retornou:

```text
docker: Error response from daemon: mkdir C:\Users\Isabel: Access is denied.

Run 'docker run --help' for more information
```

&emsp;Esse erro mostrou que o problema estava relacionado ao acesso/montagem dos diretórios do Windows pelo Docker Desktop, e não ao código do treinamento.

&emsp;**Mudança para WSL:**

&emsp;Como eu já tinha o WSL instalado, decidi utilizar o Ubuntu integrado ao Docker Desktop em vez do Git Bash. A intenção foi executar os comandos em um ambiente Linux, evitando a conversão de caminhos do Windows feita pelo Git Bash.

&emsp;Inicialmente, porém, o Ubuntu também apresentou problemas para iniciar. Ao tentar:

```powershell
wsl -d Ubuntu
```

&emsp;recebi:

```text
<3>WSL (1676 - Relay) ERROR: CreateProcessParseCommon:999: getpwnam(isabelmontenegro) failed 5
<3>WSL (1676 - Relay) ERROR: CreateProcessParseCommon:1008: getpwuid(1000) failed 5
<3>WSL (1676 - Relay) ERROR: ConfigUpdateLanguage:2580: fopen(/etc/default/locale) failed 5
<3>WSL (1676 - Relay) ERROR: operator():519: getpwuid(0) failed 5
<3>WSL (1676) ERROR: I/O error @util.cpp:1327 (UtilInitGroups)
<3>WSL (1676 - Relay) ERROR: CreateProcessCommon:742: Create process failed
```

&emsp;Usei o GPT para me ajudar a interpretar essas mensagens do terminal e entender que o problema não estava no projeto, mas na inicialização do Ubuntu dentro do WSL. Também fui orientada sobre quais comandos utilizar para verificar o estado do WSL sem apagar a distribuição.

&emsp;Primeiro verifiquei o estado do WSL:

```powershell
wsl --status
```

&emsp;que mostrou:

```text
Distribuição Padrão: Ubuntu
Versão Padrão: 2
```

&emsp;Depois:

```powershell
wsl --list --verbose
```

&emsp;e obtive:

```text
NAME              STATE           VERSION
* Ubuntu            Running         2
  docker-desktop    Running         2
```

&emsp;Isso confirmou que eu estava utilizando **WSL 2** e que o Docker Desktop também estava rodando sobre WSL 2.

&emsp;Ainda assim, o Ubuntu continuava apresentando problemas. Tentei iniciar a distribuição como `root` para verificar se o problema estava relacionado ao usuário:

```powershell
wsl -d Ubuntu -u root
```

&emsp;mas também ocorreu:

```text
getpwnam(root) failed 5
Usuário não encontrado.
Código de erro: Wsl/WSL_E_USER_NOT_FOUND
```

&emsp;Depois, com orientação do GPT, encerrei a distribuição e atualizei o WSL:

```powershell
wsl --terminate Ubuntu
wsl --update
```

&emsp;O comando `wsl --terminate Ubuntu` encerra especificamente a distribuição Ubuntu que estava com problema, enquanto `wsl --update` verifica/atualiza os componentes do WSL.

&emsp;Também foi necessário reiniciar o computador para que a atualização e as alterações no ambiente fossem aplicadas.

**Resultado após a atualização:**

&emsp;Depois de reiniciar o computador, abri novamente o Docker Desktop, esperei o serviço iniciar e testei:

```powershell
wsl -d Ubuntu
```

&emsp;Dessa vez o Ubuntu iniciou corretamente:

```text
isabelmontenegro@Isabel-0515:/mnt/c/Users/Inteli$
```

&emsp;Com isso, passei a executar os comandos pelo WSL.

&emsp;**Execução do treinamento pelo WSL:**

&emsp;Dentro do Ubuntu, acessei a pasta do projeto:

```bash
cd "/mnt/c/Users/Isabel/OneDrive/Documentos/Inteli/2026/M07/ponderada-m7-moeda"
```

&emsp;O caminho `/mnt/c/` é a forma como o WSL acessa o disco `C:` do Windows. Dessa forma, não precisei mover ou alterar o repositório que continuou no OneDrive.

&emsp;Depois confirmei os arquivos:

```bash
ls data/
```

&emsp;que mostrou:

```text
baixar_btc.py
btc_usd.csv
```

&emsp;Também testei a comunicação com o Docker pelo WSL:

```bash
docker version
```

&emsp;Com o Docker funcionando, executei finalmente o treinamento:

```bash
docker run --rm \
  -v "$(pwd)/data:/data:ro" \
  -v "$(pwd)/models:/models" \
  treino-btc
```

&emsp;Nesse comando:

* `docker run` cria e executa um container a partir da imagem `treino-btc`.
* `--rm` faz com que o container seja removido automaticamente depois que o treinamento termina, evitando deixar containers parados ocupando espaço.
* `-v "$(pwd)/data:/data:ro"` monta a pasta `data` do projeto dentro do container em `/data`. O `:ro` significa *read-only*, então o treinamento pode ler os dados, mas não modificá-los.
* `-v "$(pwd)/models:/models"` monta a pasta `models` do projeto em `/models`. Diferentemente de `data`, essa pasta não é somente leitura porque o treinamento precisa salvar o modelo gerado.
* `treino-btc` é a imagem Docker que havia sido construída anteriormente com o ambiente necessário para executar o treinamento.

&emsp;A execução apresentou:

```text
[treino] 2470 linhas, de 2020-01-01 até 2026-10-05
[treino] baseline (amanhã = hoje): MAE = 1305.76 USD
[treino] ridge: MAE = 1323.11 USD
[treino] random_forest: MAE = 1352.42 USD
[treino] melhor modelo: ridge
[treino] modelo salvo em /models/modelo_btc.joblib
```

&emsp;O treinamento utilizou **2.470 registros**, cobrindo o período de **01/01/2020 a 05/10/2026**.

&emsp;Os resultados foram:

| Modelo                   |         MAE |
| ------------------------ | ----------: |
| Baseline (amanhã = hoje) | 1305,76 USD |
| Ridge                    | 1323,11 USD |
| Random Forest            | 1352,42 USD |

&emsp;Nesse caso, o **Ridge foi o melhor entre os dois modelos testados**, com MAE de `1323,11 USD`. Porém, é importante observar que o baseline apresentou MAE menor (`1305,76 USD`). Portanto, apesar de o Ridge ter sido selecionado como o melhor modelo entre os modelos de ML avaliados, **ele não superou a estratégia simples de considerar que o preço de amanhã será igual ao preço de hoje**. Isso é um resultado importante da avaliação e mostra que o modelo ainda não apresenta ganho sobre uma referência muito simples.

&emsp;Ao final, o modelo foi exportado para:

```text
/models/modelo_btc.joblib
```

&emsp;Como `/models` está montado diretamente com a pasta `models` do projeto, esse arquivo fica disponível fora do container e pode ser utilizado posteriormente pelo backend.

**Uso de IA:**

&emsp;A IA gerou a base do `train.py`. Li linha por linha e os comentários no código explicam o que eu entendi.

&emsp;Como já relatado acima, utilizei o GPT para me auxiliar na configuração do ambiente, principalmente na interpretação dos erros do terminal e na identificação dos comandos necessários para configurar o WSL e o Docker.


### Etapa 4 - Backend de inferência

&emsp;**O que eu fiz:** escrevi/revisei `backend/app.py`, o `Dockerfile` do backend e o `docker-compose.yml`.

&emsp;**Decisões:**

* O modelo carrega uma vez quando o container sobe, e não a cada requisição.
* `/health` informa se o modelo foi carregado, permitindo verificar também se o volume com o modelo funcionou corretamente.
* Validação: exatamente 7 preços, todos positivos. Caso contrário, a API retorna erro `422`.
* No compose usei `depends_on` com `service_completed_successfully`, assim o backend só sobe depois que o treino termina e o arquivo do modelo já existe.
* Fixei a mesma versão do scikit-learn nos dois `requirements.txt`, porque um arquivo `.joblib` pode apresentar problemas de compatibilidade caso seja carregado com uma versão diferente da utilizada no treinamento.

&emsp;**Teste do backend isoladamente:**

&emsp;Primeiro construí a imagem do backend:

```bash
docker build -t backend-btc ./backend
```

&emsp;O build foi concluído com sucesso:

```text
[+] Building 42.6s (10/10) FINISHED
...
=> [5/5] COPY app.py .
...
=> naming to docker.io/library/backend-btc:latest
```

&emsp;O comando `docker build` lê o `Dockerfile` dentro de `backend/`, instala as dependências definidas no `requirements.txt`, copia o `app.py` para a imagem e, ao final, cria a imagem `backend-btc`.

&emsp;Depois executei o container:

```bash
docker run --rm -p 8000:8000 \
  -v "$(pwd)/models:/models:ro" \
  backend-btc
```

&emsp;A saída mostrou que o servidor iniciou corretamente:

```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

&emsp;Também foi possível confirmar que o modelo treinado na etapa anterior foi encontrado e carregado:

```text
[backend] modelo carregado de /models/modelo_btc.joblib
```

&emsp;O parâmetro `-p 8000:8000` fez a porta `8000` do container ficar acessível pela porta `8000` da máquina. Já o volume `-v "$(pwd)/models:/models:ro"` disponibilizou a pasta `models` dentro do container em `/models`, em modo somente leitura.

&emsp;Após iniciar o backend, abri outro terminal WSL e testei o endpoint de saúde:

```bash
curl http://localhost:8000/health
```

&emsp;O backend registrou a requisição:

```text
172.17.0.1:56902 - "GET /health HTTP/1.1" 200 OK
```

&emsp;E o terminal retornou:

```json
{"status":"ok","modelo_carregado":true}
```

&emsp;O código `200 OK` confirma que a requisição foi processada com sucesso, enquanto `"modelo_carregado":true` confirma que a API conseguiu acessar o arquivo `modelo_btc.joblib` e carregá-lo corretamente.

&emsp;**Resultado:** o backend foi construído e executado com sucesso, o modelo foi carregado corretamente e o endpoint `/health` respondeu conforme esperado.

&emsp;**Dificuldade:** não tive dificuldades durante o teste do backend.

&emsp;**Uso de IA:** a IA gerou a base do `app.py` e do compose. Entendi o fluxo: o container sobe, carrega o modelo e o `/predict` aplica a mesma transformação utilizada no treino, dividindo os preços pelo último preço antes de chamar o `predict`.

### Etapa 5 - Integração e testes

&emsp;**O que eu fiz:** integrei o modelo treinado ao backend e realizei testes para verificar o funcionamento do sistema completo. Foram testados o carregamento do modelo, a disponibilidade da API, a realização de previsões, a comunicação com o cliente Python e a validação de entradas inválidas.

&emsp;**5.1 Subir tudo**

&emsp;Para iniciar os serviços do projeto, utilizei:

```bash
docker compose up
```

&emsp;O container responsável pelo treinamento executou o processo e apresentou:

```text
[treino] 2470 linhas, de 2020-01-01 até 2026-10-05
[treino] baseline (amanhã = hoje): MAE = 1305.76 USD
[treino] ridge: MAE = 1323.11 USD
[treino] random_forest: MAE = 1352.42 USD
[treino] melhor modelo: ridge
[treino] modelo salvo em /models/modelo_btc.joblib
treino-1 exited with code 0
```

&emsp;O treinamento foi concluído normalmente e o modelo Ridge foi salvo em `/models/modelo_btc.joblib`. Em seguida, o backend foi iniciado pelo Uvicorn:

```text
backend-1  | INFO:     Started server process [1]
backend-1  | INFO:     Waiting for application startup.
backend-1  | INFO:     Application startup complete.
backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
backend-1  | [backend] modelo carregado de /models/modelo_btc.joblib
```

&emsp;A mensagem `modelo carregado de /models/modelo_btc.joblib` confirmou que o backend conseguiu acessar o artefato produzido na etapa de treinamento.

&emsp;Também foram registradas chamadas ao endpoint `/health`, todas retornando `200 OK`:

```text
backend-1  | INFO:     127.0.0.1:55990 - "GET /health HTTP/1.1" 200 OK
backend-1  | INFO:     127.0.0.1:39646 - "GET /health HTTP/1.1" 200 OK
backend-1  | INFO:     127.0.0.1:56782 - "GET /health HTTP/1.1" 200 OK
```

&emsp;Também foi registrada uma requisição de previsão processada com sucesso:

```text
backend-1  | INFO:     172.20.0.1:51628 - "POST /predict HTTP/1.1" 200 OK
```

&emsp;Esses registros confirmaram que o backend estava ativo e conseguia receber requisições.

&emsp;**5.2 Health**

&emsp;Para verificar a disponibilidade da API, utilizei:

```bash
curl http://localhost:8000/health
```

&emsp;O endpoint respondeu com sucesso, conforme indicado pelo status `200 OK` registrado nos logs do backend:

```text
"GET /health HTTP/1.1" 200 OK
```

&emsp;Esse teste foi utilizado para verificar se o servidor estava disponível antes da realização das previsões.

&emsp;**5.3 Predição**

&emsp;Com o backend disponível, realizei uma requisição diretamente ao endpoint `/predict`, utilizando sete valores de fechamento:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"ultimos_fechamentos":[60000,61000,60500,62000,63000,62500,64000]}'
```

&emsp;A resposta recebida foi:

```json
{
  "ultimo_fechamento": 64000.0,
  "previsao_proximo_fechamento": 64071.99,
  "variacao_prevista_pct": 0.11,
  "modelo": "ridge",
  "aviso": "Experimental. Não é recomendação de investimento."
}
```

&emsp;A API recebeu os sete fechamentos e retornou uma previsão de `64071.99`, partindo de um último fechamento de `64000.00`. A variação prevista foi de `0.11%`.

&emsp;O campo `"modelo": "ridge"` confirmou que a previsão foi realizada utilizando o modelo Ridge treinado na etapa anterior.

&emsp;**5.4 Cliente**

&emsp;Após os testes diretos com a API, executei o cliente Python:

```bash
python3 client/cliente.py
```

&emsp;Na primeira tentativa, o cliente apresentou:

```text
Enviando: [83622.4296875, 83553.8515625, 84853.1015625, 84497.2109375, 84763.578125, 86480.3046875, 85385.8203125]

ConnectionRefusedError: [Errno 111] Connection refused
```

&emsp;O erro `Connection refused` indicava que o cliente tentou estabelecer uma conexão com a API, mas não havia um servidor disponível naquele endereço e porta.

&emsp;Para investigar a causa, verifiquei os containers em execução:

```bash
docker ps
```

&emsp;Como não havia nenhum container ativo, utilizei:

```bash
docker ps -a
```

&emsp;A saída mostrou que os containers do projeto haviam sido encerrados:

```text
91a6e5a48b85   ponderada-m7-moeda-backend   ...   Exited (0)   ...   ponderada-m7-moeda-backend-1
8abff53b2ffd   ponderada-m7-moeda-treino    ...   Exited (0)   ...   ponderada-m7-moeda-treino-1
```

&emsp;O problema ocorreu porque eu já havia executado o `docker compose`, mas depois interrompi sua execução. Assim, quando tentei utilizar o cliente novamente, o backend não estava mais rodando para receber a requisição.

&emsp;Durante a investigação, tentei iniciar o container utilizando:

```bash
docker start backend-btc
```

&emsp;O Docker retornou:

```text
Error response from daemon: No such container: backend-btc
failed to start containers: backend-btc
```

&emsp;A mensagem indicou que não existia um container com esse nome. Ao consultar novamente `docker ps -a`, identifiquei que o container pertencente ao projeto era `ponderada-m7-moeda-backend-1`.

&emsp;Para corrigir o problema, iniciei novamente os serviços do projeto:

```bash
docker compose up
```

&emsp;O backend voltou a ser executado e apresentou:

```text
backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
backend-1  | [backend] modelo carregado de /models/modelo_btc.joblib
```

&emsp;Depois disso, executei novamente o cliente:

```bash
python3 client/cliente.py
```

&emsp;A execução foi concluída com sucesso:

```text
Enviando: [83622.4296875, 83553.8515625, 84853.1015625, 84497.2109375, 84763.578125, 86480.3046875, 85385.8203125]

Resposta: {
  "ultimo_fechamento": 85385.8203125,
  "previsao_proximo_fechamento": 85573.4,
  "variacao_prevista_pct": 0.22,
  "modelo": "ridge",
  "aviso": "Experimental. Não é recomendação de investimento."
}
```

&emsp;A resposta confirmou que o cliente conseguiu enviar os dados para o backend e receber a previsão do modelo. Nesse caso, o último fechamento informado foi `85385.82` e a previsão para o próximo fechamento foi `85573.40`, com variação prevista de `0.22%`.

&emsp;**5.5 Erro de validação**

&emsp;Por fim, testei o comportamento da API ao receber uma quantidade incorreta de valores. O modelo espera exatamente sete fechamentos, então enviei apenas três:

```bash
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"ultimos_fechamentos":[1,2,3]}'
```

&emsp;A API respondeu:

```json
{
  "detail": "Envie exatamente 7 fechamentos."
}
```

&emsp;Esse resultado confirmou que a validação de entrada está funcionando e impede que uma requisição com quantidade inadequada de dados seja processada pelo modelo.

&emsp;**Dificuldades:**

&emsp;A principal dificuldade dessa etapa foi identificar a causa do `ConnectionRefusedError` apresentado pelo cliente. Inicialmente, o erro poderia indicar um problema na API ou na comunicação com o backend. A verificação dos containers mostrou que o serviço simplesmente não estava em execução, pois eu havia interrompido anteriormente o `docker compose`.

&emsp;Também foi necessário identificar o nome correto do container, já que tentei utilizar `backend-btc`, mas esse não era o nome do container criado pelo projeto. Após verificar os containers existentes, executei novamente o `docker compose`, restabelecendo o serviço do backend.

&emsp;Depois da correção, os testes confirmaram o funcionamento das diferentes partes do sistema: o modelo foi carregado pelo backend, a API respondeu ao health check, uma previsão foi realizada diretamente pelo `curl`, o cliente Python conseguiu consumir a API e a validação rejeitou corretamente uma entrada com apenas três fechamentos.

&emsp;**Uso de IA:** Utilizei o GPT como apoio para interpretar as mensagens exibidas pelo terminal e compreender o funcionamento das etapas de integração e comunicação entre os containers.

### Resultado e limitações

&emsp;A solução foi executada com sucesso utilizando Docker Compose. O container de treinamento conseguiu ler o histórico do Bitcoin, comparar os modelos Ridge e Random Forest e salvar o modelo escolhido em `models/modelo_btc.joblib`. Em seguida, o backend conseguiu carregar esse artefato e disponibilizar os endpoints `/health` e `/predict`.

&emsp;Também foi possível realizar uma previsão diretamente pela API e por meio do cliente Python. O teste de entrada inválida confirmou que o backend rejeita requisições que não possuem exatamente sete fechamentos ou que possuem preços não positivos.

&emsp;Apesar do funcionamento da integração, existem limitações importantes. A principal é que o modelo não apresentou desempenho superior ao baseline utilizado. O Ridge apresentou MAE de 1323,11 USD, enquanto o baseline, que apenas repete o preço atual, apresentou MAE de 1305,76 USD. Portanto, não há evidência neste experimento de que o modelo de machine learning tenha produzido uma previsão melhor do que uma estratégia muito simples.

&emsp;Outra limitação é que o modelo utiliza somente os preços de fechamento dos últimos sete dias. O dataset possui a coluna de volume, mas ela não foi utilizada como entrada do modelo. Também não foram considerados outros fatores que podem influenciar o preço do Bitcoin, como outras variáveis de mercado ou acontecimentos externos.

&emsp;Além disso, a avaliação foi realizada com uma única separação cronológica de treino e teste. O experimento serve para demonstrar a solução de ponta a ponta, mas não é suficiente para afirmar que o modelo possui bom desempenho financeiro em diferentes períodos.

&emsp;Por fim, a previsão disponibilizada pela API é experimental e não deve ser utilizada como recomendação de investimento.

### O que eu aprendi

&emsp;Durante a atividade, entendi melhor a diferença entre **treinar um modelo e utilizar um modelo já treinado**. Antes, eu poderia pensar no modelo como parte da API, mas percebi que o treinamento gera um artefato separado, que pode ser salvo e depois carregado por outro serviço.

&emsp;Também entendi melhor como um volume compartilhado pode ser utilizado para fazer a comunicação de arquivos entre containers. Nesse projeto, o treinamento escreve o modelo na pasta `models` e o backend lê o mesmo arquivo. Isso permite manter os dois containers separados sem precisar colocar o modelo dentro da imagem do backend.

&emsp;Outra aprendizagem foi sobre o funcionamento do Docker Compose. Entendi que ele não serve apenas para iniciar vários containers, mas também pode definir a relação entre eles. Neste caso, o `depends_on` com `service_completed_successfully` faz com que o backend espere o treinamento terminar com sucesso antes de iniciar.

&emsp;Na parte de machine learning, entendi melhor por que uma série temporal não deve ser dividida aleatoriamente entre treino e teste. Também compreendi a função do baseline: antes de considerar um modelo de machine learning bom, preciso comparar seu resultado com uma solução simples.

&emsp;Por fim, aprendi que fazer uma aplicação funcionar envolve mais do que escrever o código. Durante a atividade precisei investigar problemas de caminhos entre Windows, Git Bash, WSL e Docker, além de entender erros de comunicação entre o cliente e o backend. A utilização da IA foi útil nesses momentos, mas foi necessário testar os comandos e conferir os resultados para entender o que estava acontecendo.

## Como executar

&emsp;Para iniciar a aplicação, execute:

```bash
docker compose up --build
```

&emsp;O treinamento será executado primeiro. Após a conclusão, o backend será iniciado automaticamente.

&emsp;Para verificar se o backend está funcionando:

```bash
curl http://localhost:8000/health
```

&emsp;Para realizar uma previsão:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"ultimos_fechamentos":[...]}'
```

&emsp;Também é possível realizar a previsão utilizando o cliente Python:

```bash
python client/cliente.py
```

&emsp;A documentação da API pode ser acessada em:

`http://localhost:8000/docs`
