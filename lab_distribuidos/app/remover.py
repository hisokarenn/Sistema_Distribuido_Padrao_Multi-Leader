import psycopg2
from app.config import SERVERS, ALL_SERVERS, LOCAL_SERVERS
from app.matricular import reavaliar_posicao

def connect_to_db(servidor_id):
    """Conecta ao banco de dados específico. Retorna None em caso de falha."""
    config = SERVERS.get(servidor_id) 
    if not config:
        return None
    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 10 
    try:
        conn = psycopg2.connect(**connect_args)
        return conn
    except psycopg2.OperationalError:
        return None

def obter_disciplina_id(conn, disciplina_nome):
    """Busca o ID e o total de vagas da disciplina pelo nome."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, vagas_totais FROM disciplinas 
            WHERE nome = %s AND (is_deleted IS NULL OR is_deleted = false)
        """, (disciplina_nome,))
        result = cursor.fetchone()
        if result:
            return result[0], result[1]
        return None, None
    finally:
        cursor.close()

def remover_aluno(lider_destino, aluno, disciplina_nome):
    """
    Remove (Soft Delete) a matrícula E reavalia a fila de espera.
    """
    conn = connect_to_db(lider_destino)
    if not conn:
        print(f"❌ Remoção falhou em {lider_destino} devido à falha de conexão.")
        return

    cursor = conn.cursor()
    
    disciplina_id, vagas_totais = obter_disciplina_id(conn, disciplina_nome)
    
    if not disciplina_id:
        print(f"❌ Falha: Disciplina '{disciplina_nome}' não encontrada ou foi removida no líder {lider_destino}.")
        conn.close()
        return

    try:
        # --- ETAPA 1: ENCONTRAR O ALUNO ---
        
        cursor.execute("""
            SELECT id FROM matriculas 
            WHERE nome_aluno = %s AND disciplina_id = %s AND status != 'REMOVIDA'
            """, (aluno, disciplina_id))
        resultado = cursor.fetchone()
        
        if not resultado:
            print(f"⚠️ Aviso: Aluno '{aluno}' não encontrado (ou já removido) em '{disciplina_nome}' no líder {lider_destino}.")
            conn.rollback()
            return
            
        id_a_remover = resultado[0]
        cursor.execute("SELECT (NOW() AT TIME ZONE 'UTC')")
        timestamp_agora = cursor.fetchone()[0]

        # --- ETAPA 2: REAVALIAR A FILA (ANTES DE REMOVER) ---
        print("\n--- Reavaliação de Fila de Espera ---")
        
        
        status_final_dummy, pos_dummy, updates_a_replicar = reavaliar_posicao(
            lider_destino, disciplina_id, vagas_totais, 
            nova_tentativa=None, 
            id_a_ignorar=id_a_remover 
        )
        # --- FIM DA CORREÇÃO ---

        if updates_a_replicar:
            print(f"Promovendo {len(updates_a_replicar)} alunos da fila de espera...")
        else:
            print("Nenhuma promoção na fila de espera necessária.")
            
        # --- ETAPA 3: APLICAR TODAS AS MUDANÇAS (1 TRANSAÇÃO) ---
        
        # 3a. Remove o aluno
        update_query_remocao = """
            UPDATE matriculas SET status = 'REMOVIDA', data_ultima_modificacao = %s
            WHERE id = %s
        """
        cursor.execute(update_query_remocao, (timestamp_agora, id_a_remover))
        
        # 3b. Registra o "Tombstone"
        tombstone_query = """
            INSERT INTO deleted_matriculas (id, timestamp) VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET timestamp = EXCLUDED.timestamp
        """
        cursor.execute(tombstone_query, (id_a_remover, timestamp_agora))

        # 3c. Aplica as promoções da fila
        update_query_fila = "UPDATE matriculas SET status = %s, data_ultima_modificacao = (NOW() AT TIME ZONE 'UTC') WHERE id = %s"
        for old_id, nome, novo_status, ts in updates_a_replicar:
             cursor.execute(update_query_fila, (novo_status, old_id))
        
        # 3d. Salva tudo (Commit 1)
        conn.commit() 
        print(f"✅ Remoção e reavaliação da fila salvas em {lider_destino}.")

        
        # --- ETAPA 4: REPLICAÇÃO ---
        print("\n--- Replicação de Remoção e Promoção da Fila ---")
        
        for servidor_id in ALL_SERVERS:
            if servidor_id == lider_destino: continue 
            replica_conn = connect_to_db(servidor_id)
            if replica_conn:
                replica_cursor = replica_conn.cursor()
                try:
                    # a) Replica o Soft Delete
                    replica_cursor.execute(update_query_remocao, (timestamp_agora, id_a_remover))
                    # b) Replica o Tombstone
                    replica_cursor.execute(tombstone_query, (id_a_remover, timestamp_agora))
                    
                    # c) Replica as promoções da fila
                    for old_id, nome, novo_status, ts in updates_a_replicar:
                        replica_cursor.execute(update_query_fila, (novo_status, old_id))

                    replica_conn.commit()
                    print(f"➡️ Replicação sucesso (Remoção + {len(updates_a_replicar)} promoções) para o servidor {servidor_id}.")
                except Exception as e:
                    print(f"❌ Erro ao replicar para {servidor_id}: {e}")
                    replica_conn.rollback()
                finally:
                    if replica_cursor: replica_cursor.close()
                    if replica_conn: replica_conn.close()
            else:
                print(f"❌ Falha de Conexão: Líder {servidor_id} inacessível para replicação.")
            
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Erro PostgreSQL durante a remoção: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def remover_matricula_menu():
    if not LOCAL_SERVERS:
        print("❌ ERRO DE CONFIGURAÇÃO: LOCAL_SERVERS não está definido no config.py.")
        return
    aluno = input("Digite o NOME do aluno a ser removido: ").strip()
    disciplina = input("Digite o NOME da disciplina: ").strip()
    if not aluno or not disciplina:
        print("❌ Remoção cancelada: Nome do aluno ou disciplina não pode ser vazio.")
        return
    lider_destino = LOCAL_SERVERS[0]
    print(f"\n⏳ Tentando remover {aluno} de '{disciplina}' via Líder {lider_destino}...")
    remover_aluno(lider_destino, aluno, disciplina)