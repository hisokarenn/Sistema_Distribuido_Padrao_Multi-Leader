# app/remover_disciplina.py
import psycopg2
from app.config import SERVERS, ALL_SERVERS, LOCAL_SERVERS

# --- NOVA FUNÇÃO DE AJUDA ---
def connect_to_db(servidor_id):
    """Conecta ao banco de dados específico. Retorna None em caso de falha."""
    config = SERVERS.get(servidor_id)
    if not config:
        return None
    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 5
    try:
        conn = psycopg2.connect(**connect_args)
        return conn
    except psycopg2.OperationalError:
        return None
# --- FIM DA FUNÇÃO DE AJUDA ---

def remover_disciplina_no_servidor(servidor_id, disciplina_nome, timestamp_agora):
    """Conecta e remove (Soft Delete) a disciplina em um único servidor."""
    config = SERVERS.get(servidor_id)
    if not config:
        return False, f"Configuração do servidor {servidor_id} não encontrada."
        
    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 5 
    
    conn = None
    try:
        conn = psycopg2.connect(**connect_args)
        cursor = conn.cursor()
        
        # 1. Encontra o ID da disciplina
        cursor.execute("SELECT id FROM disciplinas WHERE nome = %s AND (is_deleted IS NULL OR is_deleted = false);", (disciplina_nome,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return False, "Disciplina não encontrada ou já removida."

        disciplina_id = resultado[0]

        # 2. SOFT DELETE (Matrículas)
        cursor.execute("""
            UPDATE matriculas SET status = 'REMOVIDA', data_ultima_modificacao = %s
            WHERE disciplina_id = %s
            """, (timestamp_agora, disciplina_id))
        
        # 3. SOFT DELETE (Disciplina)
        cursor.execute("""
            UPDATE disciplinas SET is_deleted = true, data_ultima_modificacao = %s
            WHERE id = %s
            """, (timestamp_agora, disciplina_id))
        
        # 4. TOMBSTONE (Disciplina)
        cursor.execute("""
            INSERT INTO deleted_disciplinas (id, timestamp) 
            VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET timestamp = EXCLUDED.timestamp
            """, (disciplina_id, timestamp_agora))
        
        conn.commit()
        return True, "SUCESSO (Soft Delete)"

    except psycopg2.OperationalError:
        return False, "FALHA DE CONEXÃO (servidor offline)."
    except Exception as e:
        if conn: conn.rollback()
        return False, f"ERRO INESPERADO: {e}"
    finally:
        if conn: conn.close()

# Função principal
def remover_disciplina():
    """Função adaptada para o menu: solicita o nome da disciplina via input e tenta remover."""
    
    disciplina_nome = input("Digite o NOME da disciplina que deseja remover: ").strip()
    
    if not disciplina_nome:
        print("❌ Remoção cancelada: O nome da disciplina não pode ser vazio.")
        return

    # Pega o ID local APENAS para o feedback final
    local_id = LOCAL_SERVERS[0]
    
    print(f"\nTentando remover disciplina: '{disciplina_nome}'")
    
    all_results = {}
    
    # --- CORREÇÃO APLICADA AQUI (Lógica do timestamp) ---
    # Tenta conectar a QUALQUER líder online para gerar o timestamp
    timestamp_agora = None
    for servidor_id in ALL_SERVERS:
        conn_ts = connect_to_db(servidor_id)
        if conn_ts:
            try:
                cursor_ts = conn_ts.cursor()
                cursor_ts.execute("SELECT (NOW() AT TIME ZONE 'UTC')")
                timestamp_agora = cursor_ts.fetchone()[0]
                cursor_ts.close()
                conn_ts.close()
                print(f"✅ Timestamp para remoção gerado via Líder {servidor_id}.")
                break # Conseguiu o timestamp
            except Exception:
                if conn_ts: conn_ts.close()
                continue
    
    if timestamp_agora is None:
        print("❌ Falha: Não foi possível conectar a NENHUM líder para gerar o timestamp. (Todos estão offline?)")
        return
    # --- FIM DA CORREÇÃO ---

    # Loop de replicação (como antes)
    for servidor_id in ALL_SERVERS:
        sucesso, mensagem = remover_disciplina_no_servidor(servidor_id, disciplina_nome, timestamp_agora)
        all_results[servidor_id] = {'sucesso': sucesso, 'mensagem': mensagem}

    local_result = all_results.get(local_id) # Pega o resultado do C ou D
    
    print("\n--- Resultado da Operação ---")

    if local_result and local_result['sucesso']:
        print(f"✅ Disciplina removida (Soft Delete) com sucesso no líder local ({local_id}).")
        
        # Verifica se houve falha na replicação para A e B (que estão offline)
        for servidor_id, res in all_results.items():
            if servidor_id != local_id and not res['sucesso']:
                print(f"⚠️ Aviso: Falha na replicação para o {servidor_id}. (Motivo: {res['mensagem']})")
                
    else:
        msg = local_result['mensagem'] if local_result else f"ID do servidor local ({local_id}) não encontrado."
        print(f"❌ Falha: Não foi possível remover no líder local ({local_id}).")
        print(f"Detalhes: {msg}")
        
    print("-----------------------------\n")