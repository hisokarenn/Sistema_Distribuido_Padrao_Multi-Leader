import psycopg2
import time
from app.config import SERVERS, ALL_SERVERS, LOCAL_SERVERS 
from psycopg2.extras import execute_values 

STATUS_ACEITA = 'ACEITA'
STATUS_REJEITADA = 'REJEITADA'

def connect_to_db(servidor_id):
    config = SERVERS.get(servidor_id)
    if not config:
        raise ValueError(f"Configuração do servidor {servidor_id} não encontrada.")
    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 5
    try:
        conn = psycopg2.connect(**connect_args)
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Falha de conexão com {servidor_id}: {e}")
        return None

def obter_disciplina_id_e_vagas(conn, disciplina_nome):
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

def consultar_estado_global(disciplina_id):
    """Consulta o estado global, ignorando matrículas removidas."""
    todos_registros = []
    for servidor_id in ALL_SERVERS:
        conn = connect_to_db(servidor_id)
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT id, nome_aluno, timestamp_matricula, status
                    FROM matriculas
                    WHERE disciplina_id = %s AND status != 'REMOVIDA'
                    ORDER BY timestamp_matricula;
                """, (disciplina_id,))
                
                registros = cursor.fetchall()
                registros_corrigidos = []
                for matricula_id, nome, timestamp_db, status in registros:
                    if timestamp_db and timestamp_db.tzinfo is not None:
                        timestamp_naive = timestamp_db.replace(tzinfo=None)
                    else:
                        timestamp_naive = timestamp_db
                    registros_corrigidos.append((matricula_id, nome, timestamp_naive, status))
                todos_registros.extend(registros_corrigidos)
            except Exception as e:
                print(f"❌ Erro ao consultar servidor {servidor_id} para estado global: {e}")
            finally:
                if cursor: cursor.close()
                if conn: conn.close()
    
    registros_unicos = set(todos_registros) 
    registros_finais = list(registros_unicos)
    registros_finais.sort(key=lambda x: x[2]) 
    return registros_finais

def reavaliar_posicao(lider_destino, disciplina_id, vagas_totais, nova_tentativa=None, id_a_ignorar=None):
    """
    Reavalia o status de todos os alunos na fila.
    'lider_destino' é usado apenas para a lógica de consulta (embora aqui não seja usado).
    """
    
    registros_atuais = consultar_estado_global(disciplina_id)
    updates_a_replicar = []
    
    if id_a_ignorar:
        registros_limpos = [r for r in registros_atuais if r[0] != id_a_ignorar]
    else:
        registros_limpos = list(registros_atuais)

    if nova_tentativa:
        registros_limpos.append(nova_tentativa)
        registros_limpos.sort(key=lambda x: x[2])
        
    posicao_na_fila = 0
    status_final = None

    for i, (old_id, nome, ts, status_antigo) in enumerate(registros_limpos):
        posicao = i + 1
        status_calculado = STATUS_ACEITA if posicao <= vagas_totais else STATUS_REJEITADA
        
        is_nova_tentativa = nova_tentativa and old_id == nova_tentativa[0]
        
        if is_nova_tentativa:
            status_final = status_calculado
            posicao_na_fila = posicao
            print(f"Aluno {nome} (Novo) -> Status Final: {status_final} (Posição: {posicao}/{vagas_totais})")
            
        elif status_calculado != status_antigo:
            updates_a_replicar.append((old_id, nome, status_calculado, ts))
            print(f"Status Atualizado: {nome} mudou de {status_antigo} para {status_calculado}")
    
    return status_final, posicao_na_fila, updates_a_replicar

def matricular_aluno_menu():
    aluno_nome = input("Nome do Aluno: ").strip()
    disciplina_nome = input("Nome da Disciplina: ").strip()
    if not aluno_nome or not disciplina_nome:
        print("❌ Operação cancelada. Nome do aluno ou disciplina não pode ser vazio.")
        return
    if not LOCAL_SERVERS:
        print("❌ ERRO DE CONFIGURAÇÃO: LOCAL_SERVERS não está definido no config.py.")
        return
    lider_entrada = LOCAL_SERVERS[0]
    print(f"\n⏳ Tentando matricular {aluno_nome} (Disciplina: {disciplina_nome}) via Líder {lider_entrada}...")
    _processar_matricula(lider_entrada, aluno_nome, disciplina_nome)

def _processar_matricula(lider_entrada, aluno_nome, disciplina_nome):
    """
    Processa a matrícula.
    'lider_entrada' é o ID do servidor local que está recebendo a requisição.
    """
    
    conn = connect_to_db(lider_entrada)
    if not conn:
        print(f"❌ Matrícula falhou: Líder {lider_entrada} está offline.")
        return
    cursor = conn.cursor()
    try:
        disciplina_id, vagas_totais = obter_disciplina_id_e_vagas(conn, disciplina_nome)
        if not disciplina_id:
            print(f"❌ Matrícula falhou: Disciplina '{disciplina_nome}' não encontrada ou foi removida.")
            return

        registros_atuais = consultar_estado_global(disciplina_id)
        alunos_existentes = {nome for id, nome, ts, status in registros_atuais}
        if aluno_nome in alunos_existentes:
            print(f"❌ REJEITADA! Aluno {aluno_nome} já possui um registro de matrícula (ACEITA ou REJEITADA) na {disciplina_nome}.")
            return

        cursor.execute("SELECT gen_random_uuid(), (NOW() AT TIME ZONE 'UTC')")
        matricula_id, timestamp_utc = cursor.fetchone()
        timestamp_naive = timestamp_utc.replace(tzinfo=None)
        nova_tentativa = (matricula_id, aluno_nome, timestamp_naive, 'PENDENTE')

        status_final, posicao_na_fila, updates_a_replicar = reavaliar_posicao(
            lider_entrada, disciplina_id, vagas_totais, nova_tentativa, id_a_ignorar=None
        )
       
        
        matr_a_inserir = (
            matricula_id, disciplina_id, aluno_nome, 
            timestamp_utc, status_final, timestamp_utc 
        )
        
        insert_query = """
            INSERT INTO matriculas (id, disciplina_id, nome_aluno, timestamp_matricula, status, data_ultima_modificacao)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """
        update_query = "UPDATE matriculas SET status = %s, data_ultima_modificacao = (NOW() AT TIME ZONE 'UTC') WHERE id = %s"
        
        cursor.execute(insert_query, matr_a_inserir)
        for old_id, nome, novo_status, ts in updates_a_replicar:
            cursor.execute(update_query, (novo_status, old_id))
        conn.commit()
        
        print("\n--- Replicação de Matrícula ---")
        replicacoes_pendentes = [(insert_query, matr_a_inserir)]
        for old_id, nome, novo_status, ts in updates_a_replicar:
            replicacoes_pendentes.append((update_query, (novo_status, old_id)))

        for servidor_id in ALL_SERVERS:
            if servidor_id == lider_entrada: continue
            replica_conn = connect_to_db(servidor_id)
            if replica_conn:
                replica_cursor = replica_conn.cursor()
                try:
                    for query, data in replicacoes_pendentes:
                        replica_cursor.execute(query, data)
                    replica_conn.commit()
                    print(f"➡ Replicação SUCESSO (Nova matrícula + {len(updates_a_replicar)} updates) para o Líder {servidor_id}.")
                except Exception as e:
                    print(f"❌ Erro ao replicar para {servidor_id}: {e}")
                    replica_conn.rollback()
                finally:
                    if replica_cursor: replica_cursor.close()
                    if replica_conn: replica_conn.close()
            else:
                print(f"❌ Falha de Conexão: Líder {servidor_id} offline. (Replicação pendente)")

        print(f"\nResultado da Matrícula (Líder {lider_entrada}):")
        if status_final == STATUS_ACEITA:
            print(f"✅ SUCESSO! Aluno {aluno_nome} aceito na {disciplina_nome}. (Posição: {posicao_na_fila}/{vagas_totais})")
        else:
            print(f"❌ REJEITADA! Aluno {aluno_nome} rejeitado. (Posição: {posicao_na_fila}/{vagas_totais})")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Erro PostgreSQL durante a matrícula: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()