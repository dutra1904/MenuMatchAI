# Arquitetura

O MenuMatch separa o que é restrição do que é semelhança de texto. Alergia, dieta, teto de preço, tempo e zona de entrega eliminam pratos antes do ranqueamento. O que sobra é ordenado pela proximidade do texto do prato com a frase do cliente.

## Ingestão

1. `backend/app/data/menus.json` traz restaurantes e pratos fictícios: ingredientes, alérgenos, preço, tempo e tipo (prato, entrada, bebida, sobremesa).
2. Na subida, `catalog.sync_catalog` grava isso no banco. Um hash do arquivo evita regravar quando nada mudou.
3. `seed_orders.json` cria um histórico só se a tabela de pedidos estiver vazia. Os totais passam pela mesma função de preço dos pedidos ao vivo.
4. `embeddings.document_text` monta o documento: nome, descrição, ingredientes, categoria, casa e dieta.
5. `SentenceEmbedder` gera vetores de 384 dimensões com o MiniLM multilíngue (ONNX). `VectorStore` grava `vectors.npy` e `index.faiss`.
6. O classificador multirrótulo (`services/classifier.py`) treina em `data/tag_train.json` e sugere tags a partir da descrição. Alergia e dieta do JSON continuam sendo a trava da busca.
7. O manifesto (`documentos`, dimensões, horário) vai para `backend/.cache/index_meta.json`.

`EMBEDDING_PROVIDER=tfidf` ainda existe como índice esparso local, sem baixar modelo. Não se mistura vetor TF-IDF com vetor MiniLM: a assinatura do índice inclui o nome do modelo.

Restrições não são escritas artificialmente em todo prato livre de lactose. O filtro é que garante a restrição. O vetor descreve a comida.

## Busca

`MenuIndex.search` aplica, nesta ordem:

- alérgenos proibidos (`lactose`, `gluten`, `egg`, `shellfish`)
- dieta `vegan` ou `vegetarian`
- preço máximo
- tempo máximo de preparo
- zona atendida pelo restaurante
- ids excluídos, no caso de "outra opção"

A consulta é expandida com termos próximos (rápido → express, pizza → italiana), embedada e comparada por cosseno no FAISS (`IndexFlatIP` sobre vetores normalizados). Um ajuste pequeno favorece prato principal, casa com nota mais alta e, quando a frase pede, pressa ou preço baixo. Entrada, bebida e sobremesa só sobem quando a frase fala delas.

Se o filtro de tempo ou de preço esvazia o resultado, a busca abre um degrau: primeiro solta o tempo, depois soma R$ 15 ao teto. Alergia e dieta não são relaxadas. A resposta avisa quando isso acontece.

## Agente e ferramentas

Duas ferramentas, com o mesmo código nos dois modos:

| Ferramenta | Entrada | Saída |
| --- | --- | --- |
| `search_menu` | texto, preço, tempo, alérgenos, dieta, zona | pratos com id, preço, tempo e casa |
| `calculate_order` | ids, quantidades, zona | subtotal, taxa, total, JSON do pedido |

Taxas: Centro R$ 5,90, Zona Norte R$ 7,50, Zona Leste R$ 8,50, Zona Sul R$ 8,90, Zona Oeste R$ 9,90. Itens de restaurantes diferentes são recusados. A zona precisa ser atendida pela casa.

O orquestrador local lê a frase, chama `search_menu` e, quando a pessoa está pedindo comida e não só listando o cardápio, chama `calculate_order` com o melhor prato. "Confirma" grava o rascunho da sessão. "Outra" tira o último prato da lista e repete a busca com a frase anterior.

Com chave, `langchain_agent.py` publica as mesmas funções para o Gemini ou para o GPT. O prompt manda o modelo não inventar prato. Se a chamada falha, estoura o tempo ou termina sem ferramenta, o orquestrador local responde no lugar. Cada resposta informa `provider`, `tools_used` e `latency_ms`.

Confirmar pelo botão da interface chama `POST /api/orders`. O servidor relê o preço no catálogo. O JSON exibido no painel lateral é o corpo do pedido, versão `1.0`.

## Latência

- O índice fica em memória. A busca não sai da máquina.
- A matriz é montada uma vez na subida. Trinta pratos não justificam reconstruir a cada pergunta.
- A chamada de LLM não bloqueia o produto: a falha cai no caminho local, que usa as ferramentas em processo.
- A média das últimas cem respostas da sessão da API aparece no painel.

## API

| Método | Caminho | Uso |
| --- | --- | --- |
| `GET` | `/api/health` | Índice e provedor configurado |
| `GET` | `/api/restaurants` | Casas do catálogo |
| `GET` | `/api/menu` | Busca direta, sem o agente |
| `POST` | `/api/chat` | Conversa |
| `POST` | `/api/orders` | Confirma e grava |
| `GET` | `/api/analytics` | Painel |

## Banco

SQLite em `backend/menumatch.db` é o padrão. `DATABASE_URL` troca para PostgreSQL sem mudar o código das rotas. Pedidos guardam nome e preço do item, então o histórico do painel não depende do texto atual do cardápio.

`infra/postgres_pgvector.sql` descreve a evolução: a coluna `embedding vector(384)` e um índice HNSW com `vector_cosine_ops`. Hoje a comparação por cosseno acontece no FAISS, no processo da API, o que basta para o catálogo desta demo.

## Painel

Os pedidos semeados e os confirmados na conversa alimentam:

- pedidos, receita e ticket de hoje
- parcela de pedidos com restrição alimentar
- itens mais pedidos em sete dias
- minutos economizados, calculados como `pedidos de hoje × (4,2 − 0,7)`

4,2 e 0,7 são parâmetros (`BROWSE_MINUTES` e `AGENT_MINUTES`), não uma medição de campo. O painel deixa isso escrito.
