import psycopg2
import uuid 
from psycopg2.extras import execute_values 
from app.config import SERVERS, ALL_SERVERS

def connect_to_db(servidor_id):
    """Conecta ao banco de dados específico."""
    config = SERVERS.get(servidor_id)
    if not config:
        print(f"❌ Configuração do servidor {servidor_id} não encontrada.")
        return None

    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 5

    try:
        conn = psycopg2.connect(**connect_args)
        return conn
    except psycopg2.OperationalError as e:
        return None


def _adicionar_disciplina_core(disciplina_nome: str, vagas: int):
    """
    [FUNÇÃO INTERNA] Contém a nova lógica de replicação Multi-Líder.
    """

    print(f"--- Tentando adicionar disciplina: {disciplina_nome} ({vagas} vagas) ---")

    # 1. Gerar os dados UNIVERSAIS para esta disciplina
    disciplina_uuid = str(uuid.uuid4())
    
    # --- CORREÇÃO APLICADA AQUI ---
    # Tenta conectar a QUALQUER líder disponível para gerar um timestamp
    timestamp_agora = None
    for servidor_id in ALL_SERVERS:
        conn_check = connect_to_db(servidor_id)
        if conn_check:
            try:
                cursor_check = conn_check.cursor()
                cursor_check.execute("SELECT (NOW() AT TIME ZONE 'UTC')")
                timestamp_agora = cursor_check.fetchone()[0]
                cursor_check.close()
                conn_check.close()
                print(f"✅ Timestamp gerado via Líder {servidor_id}.")
                break # Sai do loop assim que conseguir um timestamp
            except Exception:
                if conn_check: conn_check.close()
                continue
    
    if timestamp_agora is None:
         print("❌ Falha: Não foi possível conectar a NENHUM líder para gerar timestamp. (Ambos estão offline?)")
         return
    # --- FIM DA CORREÇÃO ---

    # Dados completos a serem replicados (de acordo com o init.sql)
    dados_disciplina = (
        disciplina_uuid, 
        disciplina_nome, 
        vagas, 
        False, # is_deleted
        timestamp_agora # data_ultima_modificacao
    )

    # 2. Preparar a consulta de MERGE (INSERT ... ON CONFLICT)
    colunas_query = "(id, nome, vagas_totais, is_deleted, data_ultima_modificacao)"
    update_set = """
        nome = EXCLUDED.nome, 
        vagas_totais = EXCLUDED.vagas_totais, 
        is_deleted = EXCLUDED.is_deleted, 
        data_ultima_modificacao = EXCLUDED.data_ultima_modificacao
    """
    update_where = "disciplinas.data_ultima_modificacao < EXCLUDED.data_ultima_modificacao"

    query = f"""
        INSERT INTO disciplinas {colunas_query}
        VALUES %s 
        ON CONFLICT (id) DO UPDATE SET {update_set}
        WHERE {update_where};
    """

    success_count = 0
    total_servers = len(ALL_SERVERS)

    # 3. Tentar aplicar em TODOS os líderes
    for servidor_id in ALL_SERVERS:
        conn = connect_to_db(servidor_id)

        if not conn:
            print(f"❌ Falha de Conexão: O servidor {servidor_id} está inacessível. (Sincronização manual será necessária)")
            continue

        cursor = conn.cursor()

        try:
            execute_values(cursor, query, [dados_disciplina])
            conn.commit()
            success_count += 1

        except psycopg2.Error as e:
            conn.rollback()
            print(f"❌ Erro PostgreSQL ao adicionar em {servidor_id}: {e}")
        except Exception as e:
            print(f"❌ Erro inesperado em {servidor_id}: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if success_count == total_servers:
        print(f"\n✅ Sucesso: Disciplina '{disciplina_nome}' foi adicionada e replicada em TODOS os líderes.")
    elif success_count > 0:
        print(f"\n⚠ Aviso: Disciplina '{disciplina_nome}' adicionada em {success_count} de {total_servers} líderes.")
        print("   (Rode a Opção 10 'Heal' para forçar a sincronização nos nós offline)")
    else:
        print(f"\n❌ Falha: Disciplina '{disciplina_nome}' não foi adicionada em nenhum líder.")
        

def adicionar_disciplina():
    """
    [FUNÇÃO PRINCIPAL] Lida com a entrada do usuário e chama a lógica de DB. 
    """
    try:
        nome = input("Digite o nome da disciplina: ").strip()
        vagas_str = input("Digite o número de vagas: ").strip()
        
        if not nome:
            print("❌ O nome da disciplina não pode ser vazio.")
            return

        vagas = int(vagas_str)

        if vagas <= 0:
            print("❌ O número de vagas deve ser positivo.")
            return

        _adicionar_disciplina_core(nome, vagas)
        
    except ValueError:
        print("❌ Entrada inválida. O número de vagas deve ser um número inteiro positivo.")
    except Exception as e:
        print(f"❌ Ocorreu um erro: {e}")