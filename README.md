# 🛠️ Laboratório de Prototipagem de Padrões Distribuídos - Multi-Líder (Nós Múltiplos)

## 🔗 Visão Geral do Projeto

Este repositório contém a prototipagem de um **Sistema Distribuído Multi-Líder** que simula um Catálogo de Disciplinas e Matrículas em um ambiente de múltiplas máquinas (Nós).

NO objetivo principal é demonstrar o funcionamento prático de um padrão de replicação/distribuição, focando na **Alta Disponibilidade (AP)** e na **Tolerância a Falhas**

### 🎯 Padrão Implementado: Replicação Multi-Líder

No padrão Multi-Líder, cada nó (Líder A, Líder B, etc.) aceita operações de escrita e leitura. A replicação é assíncrona, o que garante alta disponibilidade (os nós podem falhar, mas o sistema continua aceitando operações).

-----

## ⚙️ Arquitetura e Tecnologias

| Componente | Tecnologia | Função no Protótipo |
| :--- | :--- | :--- |
| **Bancos de Dados** | PostgreSQL (Docker) | SGBD real que armazena os dados.Cada nó é uma instância PostgreSQL independente. |
| **Replicação/Lógica** | Python (Scripts de Cliente) | O "cérebro" do sistema. É responsável por: <br> • **Replicar** as operações para todos os nós. <br> • **Resolver Conflitos** (Merge). <br> • **Promover** alunos da lista de espera. |
| **Orquestração** | Docker / Docker Compose |Usado para simular e gerenciar cada nó (Líder A, Líder B, etc.). |
| **Identificação** | UUIDs | Usado como chave primária para todas as entidades (disciplinas e matrículas) para evitar colisões de ID durante escritas simultâneas. |

-----

## 🛑 Desafios Chave (Conflitos Resolvidos)

Este protótipo foca em resolver dois problemas centrais do Multi-Líder:

1.  **A Fila de Espera Inconsistente (Bug de Lógica):**

**Problema:** Quando um aluno aceito é removido, o aluno rejeitado subsequente na fila (`REJEITADA`) não era promovido a `ACEITA` automaticamente.
**Solução:** O script `remover.py` foi corrigido para, após a deleção, chamar a lógica de `reavaliar_posicao` (o "juiz" do sistema) para que o próximo aluno seja promovido instantaneamente.

2.  **Ressurreição de Dados (`DELETE` vs. `CREATE`):**

**Problema:** O uso de `DELETE` (apagar de verdade) levaria à "ressurreição de dados", pois um nó offline que volta a ficar online restauraria o dado que o outro nó havia apagado.
**Solução (Soft Delete e Tombstones):** O sistema utiliza **Deleção Lógica (Soft Delete)** Em vez de apagar, ele marca a coluna `is_deleted = true` ou o `status = 'REMOVIDA'`. Isso permite que a sincronização (`sincronizacao.py`) entenda a diferença entre um dado que está "faltando" e um dado que foi "removido intencionalmente.

-----

## 🚀 Como Executar o Protótipo

### 1\. Pré-Requisitos

  * Docker e Docker Compose instalados.
  * Python 3.11.0 (foi utilizado) e a biblioteca `psycopg2` e `prettytable`.
  * As máquinas devem estar na mesma rede para que os IPs sejam acessíveis.

### 2\. Configuração por Máquina (Setup Distribuído)

**Atenção:** Os scripts de lógica (`matricular.py`, `sincronizacao.py`, etc.) são idênticos em todas as máquinas. A diferenciação é feita apenas por configuração.

1.  **`app/config.py`:**
Atualize os IPs de todos os líderes (A, B, C, D...).
Defina a linha `LOCAL_SERVERS = ['X']` para identificar a máquina local (ex: `['A']` para a Máquina A).
2.  **`docker-compose.yml`:**
Este arquivo deve ser modificado em cada máquina para refletir o nome do serviço (ex: `lider-a`, `lider-b`) e a porta correspondente (ex: `5432`, `5433`, etc.).
3.  **Inicialização:** Copie a pasta `init-scripts/` (com o `init.sql`) para o diretório raiz de cada projeto.

### 3\. Comandos de Inicialização

1.  **Limpar e Recriar DBs (Se a estrutura SQL foi alterada):**
    ```bash
    docker-compose down -v
    docker-compose up -d
    ```
2.  **Iniciar a Aplicação:**
    ```bash
    python main.py
    ```
    
-----

## 📝 Demonstrações de Validação (Roteiro)

O sistema deve ser validado com uma **demonstração interativa ao vivo**.

| Cenário de Teste | Objetivo | Resultado Esperado |
| :--- | :--- | :--- |
|**Escrita e Replicação**| Inserir um dado no Líder A e verificar se ele aparece imediatamente no Líder B (via Opção 2 ou 5). | Dado replicado e visível em todos os líderes online]. |
|**Simulação de Falhas** | Desligar o Docker do **Líder A**. Adicionar dados no Líder B. |Líder B continua aceitando escritas (Alta Disponibilidade). |
|**Recuperação e Heal**  |Ligar o Docker do Líder A. Rodar a **Opção 10 (Forçar Sincronização)**. |O Líder A "puxa" (pull) os dados que perdeu. Ambos os líderes ficam sincronizados e operacionais. |
| **Promoção da Fila** | Adicionar 3 alunos em 2 vagas (Aluno 3 fica `REJEITADA`). Remover Aluno 1 (`ACEITA`). | O Aluno 3 deve ser promovido automaticamente para `ACEITA`. |
